"""
SHOWCASE EXAMPLE — 날짜별 실버 → 시즌 투구 마트.

production의 41열 중 핵심 열만 재구성한 실행 예제입니다.
입력 완결성 검사, R2 업로드, mart_build 장부와 버전 관리는 호출부의 책임이며
여기서는 행 필터·열 이름·정렬과 읽을 때의 경기 유형 선택을 보여줍니다.

실행에는 duckdb가 필요합니다: python examples/pitch-mart.py
"""

from pathlib import Path
from tempfile import TemporaryDirectory

ROW_GROUP_SIZE = 20_000
COLUMNS = {
    "game_pk": "game_pk",
    "game_date": "game_date",
    "game_type": "game_type",
    "play_matchup_pitcher_id": "pitcher_id",
    "play_about_atBatIndex": "at_bat_index",
    "pitchNumber": "pitch_number",
    "pitchData_coordinates_pX": "plate_x",
    "pitchData_startSpeed": "start_speed",
}


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def select_sql(silver_glob: str) -> str:
    columns = ", ".join(
        f'"{source}" as "{target}"' for source, target in COLUMNS.items()
    )
    return (
        f"select {columns} from read_parquet({sql_literal(silver_glob)}) "
        "where is_pitch "
        'order by "play_matchup_pitcher_id", "game_date", "game_pk", '
        '"play_about_atBatIndex", "pitchNumber"'
    )


def demo() -> None:
    import duckdb

    with TemporaryDirectory() as directory:
        root = Path(directory)
        con = duckdb.connect()
        try:
            con.execute("""
                create table silver as
                select * from (values
                    (2, DATE '2026-09-08', NULL, 20, 1, 1, 0.1, 99.5, true),
                    (1, DATE '2026-09-07', 'R', 10, 1, 2, 0.2, 98.1, true),
                    (1, DATE '2026-09-07', 'R', 10, 1, 1, 0.3, 97.2, true),
                    (1, DATE '2026-09-07', 'R', 10, 1, NULL, NULL, NULL, false),
                    (3, DATE '2026-09-08', 'A', 10, 1, 1, 0.4, 96.4, true)
                ) t(game_pk, game_date, game_type, play_matchup_pitcher_id,
                    play_about_atBatIndex, pitchNumber,
                    pitchData_coordinates_pX, pitchData_startSpeed, is_pitch)
            """)
            # 날짜별 파일 두 개를 준비합니다.
            for day in ("2026-09-07", "2026-09-08"):
                target = sql_literal(str(root / f"silver-{day}.parquet"))
                con.execute(
                    f"copy (select * from silver where game_date = DATE '{day}') "
                    f"to {target} (format parquet)"
                )

            query = select_sql(str(root / "silver-*.parquet"))
            output = root / "pitches.parquet"
            con.execute(
                f"copy ({query}) to {sql_literal(str(output))} "
                f"(format parquet, compression zstd, row_group_size {ROW_GROUP_SIZE})"
            )
            con.execute(
                f"create view mart as select * from read_parquet({sql_literal(str(output))})"
            )
            assert con.execute("select count(*) from silver").fetchone()[0] == 5
            assert con.execute("select count(*) from mart").fetchone()[0] == 4
            assert [r[0] for r in con.execute("describe mart").fetchall()] == list(COLUMNS.values())
            # 저장된 행을 읽어 투수·날짜·타석·투구 순 정렬을 확인합니다.
            keys = con.execute(
                "select pitcher_id, game_date, game_pk, at_bat_index, pitch_number from mart"
            ).fetchall()
            assert keys == sorted(keys)
            assert con.execute(
                "select start_speed from mart where game_pk = 2"
            ).fetchone()[0] == 99.5
            # NULL 유형은 남기고 올스타만 제외합니다. 빌드에서는 모두 보존합니다.
            assert con.execute(
                "select count(*) from mart where game_type is distinct from 'A'"
            ).fetchone()[0] == 3
            assert con.execute("select count(*) from mart where game_type = 'A'").fetchone()[0] == 1
            print("ok — 날짜 파일 결합·투구만 선택·열 매핑·정렬·값 보존·NULL 경기 유형")
        finally:
            con.close()


if __name__ == "__main__":
    demo()
