"""브론즈 날짜 파일 하나 → 실버 날짜 파일 하나. SQL 한 문장을 조립하는 예제.

production 코드를 설명하기 위해 축약한 것이다. 실제 열은 128개이고 여기서는 몇 개만 둔다.

핵심 판단 셋.

1. **실버는 고정 스키마다.** 브론즈는 온 대로 담아 파일마다 열이 다르다(상황이 있을 때만
   오는 열). 실버는 어느 날이든 같은 열·같은 타입이어야 하므로, 그날 파일에 있는 열은
   `cast`, 없는 열은 `NULL::타입`으로 select 목록을 조립한다.
2. **행을 거르지 않는다.** 투구가 아닌 행(교체·견제)은 파생 열이 `False`가 아니라 NULL이다.
   `False`로 두면 `avg(swung)`의 분모가 부푼다.
3. **파생 식도 cast된 열을 참조한다.** 원본 열을 그대로 쓰면 브론즈가 그 열을 VARCHAR로
   추론한 날 `between 1 and 9`가 cast 오류가 아니라 바인딩 오류로 먼저 터져서, 열 이름이
   실린 실패 문구를 만들 수 없다.
"""

# 브론즈에서 그대로 가져오는 열. 이름은 브론즈 평탄화 경로 그대로다(이름이 곧 출처).
KEPT: dict[str, str] = {
    "game_pk": "BIGINT",
    "type": "VARCHAR",
    "index": "BIGINT",
    "pitchNumber": "BIGINT",
    "play_about_atBatIndex": "BIGINT",
    "details_call_code": "VARCHAR",
    "pitchData_zone": "BIGINT",
    "pitchData_startSpeed": "DOUBLE",
    "play_result_eventType": "VARCHAR",
    "details_violation_type": "VARCHAR",  # 피치 클록 위반이 없는 날은 열 자체가 없다
}

# 화면 코드와 같은 상수를 쓴다. 창고와 화면이 다른 규칙으로 스윙을 세면 스윙률이 두 값이 된다.
SWING_CALLS = frozenset({"X", "D", "E", "F", "T", "L", "O", "S", "W", "M"})
WHIFF_CALLS = frozenset({"S", "W", "M"})


def _sql_list(codes) -> str:
    return ", ".join(f"'{code}'" for code in sorted(codes))


def select_sql(present: dict[str, str], *, bronze_path: str, season: int) -> str:
    """`present`는 그날 브론즈 파일의 열 → 타입 (`describe`로 얻는다)."""

    def col(name: str) -> str:
        kind = KEPT[name]
        return f'cast(b."{name}" as {kind})' if name in present else f"NULL::{kind}"

    kept = [f'{col(name)} as "{name}"' for name in KEPT]
    is_pitch = f"{col('type')} = 'pitch'"
    last_pitch = (
        f"{col('pitchNumber')} = max({col('pitchNumber')}) "
        f'over (partition by b."game_pk", {col("play_about_atBatIndex")})'
    )
    derived = [
        f'{season}::SMALLINT as "season"',
        f'{is_pitch} as "is_pitch"',
        f'case when {is_pitch} then {col("details_call_code")} in ({_sql_list(SWING_CALLS)}) end as "swung"',
        f'case when {is_pitch} then {col("details_call_code")} in ({_sql_list(WHIFF_CALLS)}) end as "whiffed"',
        f'case when {is_pitch} then {col("pitchData_zone")} between 1 and 9 end as "in_zone"',
        f'case when {is_pitch} and {last_pitch} then {col("play_result_eventType")} end as "pa_result"',
    ]
    columns = ",\n    ".join(kept + derived)
    return f"select\n    {columns}\nfrom read_parquet('{bronze_path}') b"


def demo() -> None:
    """작은 브론즈 표를 만들어 실제로 돌린다. 행 수가 같고 파생이 맞는지 확인한다."""
    import duckdb

    con = duckdb.connect()
    # 한 타석: 투구 두 개(마지막이 인플레이 안타)와 투수 교체 하나. 위반 열은 이날 없다.
    con.execute(
        """
        create table bronze as select * from (values
            (1, 'pitch',  0, 1, 4, 'S', 5,  98.9, 'single'),
            (1, 'pitch',  1, 2, 4, 'D', 8, 97.4, 'single'),
            (1, 'action', 2, NULL, 4, NULL, NULL, NULL, 'single')
        ) t("game_pk", "type", "index", "pitchNumber", "play_about_atBatIndex",
            "details_call_code", "pitchData_zone", "pitchData_startSpeed", "play_result_eventType")
        """
    )
    con.execute("copy bronze to 'bronze.parquet' (format parquet)")
    present = {row[0]: row[1] for row in con.execute("describe bronze").fetchall()}

    sql = select_sql(present, bronze_path="bronze.parquet", season=2026)
    # select를 임시 테이블로 먼저 만든다. count(*)만 하면 DuckDB가 안 쓰는 열의 cast를 걷어내
    # 검사가 안 된다. 테이블로 만들면 전부 평가되어 cast 실패가 여기서 난다 — 파일을 쓰기 전에.
    con.execute(f"create table silver as {sql}")

    assert con.execute("select count(*) from silver").fetchone()[0] == 3  # 행을 거르지 않는다
    assert "details_violation_type" in {r[0] for r in con.execute("describe silver").fetchall()}  # 없던 열도 있다
    rows = con.execute('select "type", swung, whiffed, in_zone, pa_result from silver order by "index"').fetchall()
    assert rows[0] == ("pitch", True, True, True, None)  # 헛스윙, 존 안, 마지막 투구 아님
    assert rows[1] == ("pitch", True, False, True, "single")  # 인플레이, 마지막 투구라 결과가 붙는다
    assert rows[2] == ("action", None, None, None, None)  # 투구가 아니면 파생이 NULL

    import os

    os.remove("bronze.parquet")
    print("ok — 3행 그대로, 파생 열 정상, 없던 열은 NULL")


if __name__ == "__main__":
    demo()
