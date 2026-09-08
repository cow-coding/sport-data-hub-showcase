"""
SHOWCASE EXAMPLE — 마트 우선, 최신 등판 보완, 원천 폴백.

production 구조를 설명하기 위한 독립 실행 예제입니다. 네트워크·자격증명 없이
주입한 함수로 흐름을 확인합니다. 실제 PitchEvent, 장부/응답 캐시, DuckDB 연결,
좌표 필터와 타석 결과 복원은 생략했습니다.

마트가 있어도 등판 목록 조회는 남습니다. None은 마트를 쓸 수 없다는 뜻이고,
빈 by_game은 정상 조회 결과입니다. 둘을 구분해야 불필요한 전체 폴백을 막습니다.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date
from typing import Callable

GameKey = tuple[date, int]
Events = list[str]  # production에서는 투구 이벤트 모델


@dataclass
class MartSnapshot:
    by_game: dict[GameKey, Events]
    through_date: date


def season_pitches(
    player_id: int,
    season: int,
    *,
    load_mart: Callable[[int, int], MartSnapshot | None],
    list_games: Callable[[int, int], list[GameKey]],
    fetch_game: Callable[[int, int], Events],
    limit: int | None = None,
) -> Events:
    """마트 범위와 최근 등판을 합친 뒤 최근 N경기 또는 시즌 전체를 반환합니다."""
    if limit is not None and limit < 1:
        raise ValueError("limit must be positive")

    # 이 어댑터는 창고 미설정·미구축·조회 실패를 None으로 알립니다.
    snapshot = load_mart(player_id, season)
    games = sorted(set(list_games(player_id, season)))

    def fetch(key: GameKey) -> tuple[GameKey, Events]:
        try:
            return key, fetch_game(key[1], player_id)
        except Exception:
            # 일부 경기 실패는 나머지 분포를 막지 않습니다.
            # 실제 서비스도 실패 결과를 캐시에 넣지 않고 다음 요청에서 다시 시도합니다.
            return key, []

    if snapshot is None:
        wanted = games[-limit:] if limit is not None else games
        if not wanted:
            return []
        with ThreadPoolExecutor(max_workers=min(8, len(wanted))) as pool:
            by_game = dict(pool.map(fetch, wanted))
    else:
        # 공유된 마트 결과를 변경하지 않도록 복사합니다.
        by_game = dict(snapshot.by_game)
        for key in games:
            if key[0] > snapshot.through_date:
                _, events = fetch(key)
                if events:
                    by_game[key] = events

    ordered = sorted(by_game)
    if limit is not None:
        ordered = ordered[-limit:]
    return [event for key in ordered for event in by_game[key]]


def demo() -> None:
    old = (date(2026, 9, 1), 101)
    boundary = (date(2026, 9, 7), 102)
    recent = (date(2026, 9, 8), 103)
    snapshot = MartSnapshot(
        {old: ["old"], boundary: ["boundary"]}, date(2026, 9, 7)
    )
    calls = []

    def fetch(game_id: int, player_id: int) -> Events:
        calls.append(game_id)
        return [f"upstream:{game_id}"]

    def games(player_id: int, season: int) -> list[GameKey]:
        return [recent, old, boundary]

    result = season_pitches(
        1, 2026, load_mart=lambda *_: snapshot, list_games=games, fetch_game=fetch
    )
    assert result == ["old", "boundary", "upstream:103"]
    assert calls == [103]  # 경계 날짜는 다시 받지 않습니다.
    assert recent not in snapshot.by_game

    calls.clear()
    result = season_pitches(
        1, 2026, load_mart=lambda *_: snapshot, list_games=games,
        fetch_game=fetch, limit=1
    )
    assert result == ["upstream:103"] and calls == [103]

    calls.clear()
    result = season_pitches(
        1, 2026, load_mart=lambda *_: None, list_games=games, fetch_game=fetch
    )
    assert sorted(calls) == [101, 102, 103]
    assert result == ["upstream:101", "upstream:102", "upstream:103"]

    calls.clear()
    empty = MartSnapshot({}, date(2026, 9, 8))
    assert season_pitches(
        1, 2026, load_mart=lambda *_: empty, list_games=games, fetch_game=fetch
    ) == []
    assert calls == []  # 정상적인 빈 마트를 장애로 오해하지 않습니다.

    def fail_recent(game_id: int, player_id: int) -> Events:
        if game_id == 103:
            raise OSError("simulated upstream failure")
        return ["ok"]

    assert season_pitches(
        1, 2026, load_mart=lambda *_: snapshot, list_games=games,
        fetch_game=fail_recent
    ) == ["old", "boundary"]
    assert season_pitches(
        1, 2026, load_mart=lambda *_: None, list_games=games,
        fetch_game=fail_recent
    ) == ["ok", "ok"]
    print("ok — 마트 우선·경계 날짜·최근 N경기·폴백·빈 결과·부분 실패")


if __name__ == "__main__":
    demo()
