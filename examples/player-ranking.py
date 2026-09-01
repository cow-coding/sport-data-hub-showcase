"""
SHOWCASE EXAMPLE

사용자 행동을 인기 선수 기능으로 연결하는 구조를 단순화한 예제입니다.
핵심 판단은 '검색 횟수'가 아니라 '실제로 어떤 선수 상세를 열었는가'를
product event로 저장하는 것입니다.
"""

from datetime import timedelta

from sqlalchemy import func, select


def record_player_view(session, *, player_id: int, source: str, query: str | None):
    session.add(
        PlayerView(
            player_id=player_id,
            source=source,
            query=query,
        )
    )
    session.commit()


def ranked_player_ids(session, *, window_days: int = 7, limit: int = 10):
    since = func.now() - timedelta(days=window_days)

    rows = session.execute(
        select(
            PlayerView.player_id,
            func.count().label("views"),
        )
        .where(PlayerView.viewed_at >= since)
        .group_by(PlayerView.player_id)
        .order_by(func.count().desc())
        .limit(limit)
    ).all()

    return [row.player_id for row in rows]


def popular_players(session):
    # ranking 자체는 DB에서 최신 상태를 계산한다.
    ids = ranked_player_ids(session)

    # 선수 프로필은 ranking보다 변화가 느리므로 player 단위 cache를 재사용한다.
    return player_service.get_players(ids)
