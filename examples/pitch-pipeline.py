"""
SHOWCASE EXAMPLE

한 선수의 시즌 투구 데이터를 만드는 흐름을 단순화한 예제입니다.

1) 선수의 등판 경기 목록을 얻고
2) 경기별 play-by-play를 병렬 조회하며
3) 경기 단위 cache를 재사용하고
4) 일부 경기 실패가 전체 결과를 막지 않도록 합니다.
"""

from concurrent.futures import ThreadPoolExecutor


MAX_WORKERS = 8


def fetch_game_pitches(game_id: int, player_id: int):
    key = (game_id, player_id)

    cached = game_cache.get(key, _MISS)
    if cached is not _MISS:
        return cached

    try:
        play_by_play = mlb_client.get_play_by_play(game_id)
        pitches = extract_player_pitches(play_by_play, player_id)
    except Exception:
        # 한 경기의 원천 API 실패가 전체 시즌 화면 실패로 번지지 않게 한다.
        # 실패 결과는 cache하지 않아 다음 요청에서 다시 시도할 수 있다.
        return []

    game_cache.set(key, pitches)
    return pitches


def season_pitches(player_id: int, season: int):
    game_ids = mlb_client.get_pitching_game_ids(player_id, season)

    if not game_ids:
        return []

    workers = min(MAX_WORKERS, len(game_ids))

    with ThreadPoolExecutor(max_workers=workers) as pool:
        per_game = pool.map(
            lambda game_id: fetch_game_pitches(game_id, player_id),
            game_ids,
        )

    return [
        pitch
        for game_pitches in per_game
        for pitch in game_pitches
    ]
