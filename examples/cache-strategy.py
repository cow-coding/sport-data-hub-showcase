"""
SHOWCASE EXAMPLE

실제 private repository의 cache 설계를 설명하기 위해 단순화한 예제입니다.
구현은 Claude Code를 활용해 진행했으며, 이 파일의 목적은 코드 저작량이 아니라
제가 선택한 cache boundary와 운영 조건을 설명하는 것입니다.
"""

from threading import Lock
from cachetools import TTLCache


_MISS = object()


class BoundedCache:
    def __init__(self, *, ttl_seconds: int, maxsize: int):
        self._store = TTLCache(maxsize=maxsize, ttl=ttl_seconds)
        self._lock = Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key, default=None):
        with self._lock:
            try:
                value = self._store[key]
            except KeyError:
                self.misses += 1
                return default

            self.hits += 1
            return value

    def set(self, key, value):
        with self._lock:
            self._store[key] = value

    def stats(self):
        with self._lock:
            return {
                "size": len(self._store),
                "maxsize": self._store.maxsize,
                "hits": self.hits,
                "misses": self.misses,
            }


# 데이터마다 변화 주기와 payload가 다르기 때문에 같은 정책을 쓰지 않는다.
player_cache = BoundedCache(ttl_seconds=60 * 60, maxsize=512)
league_cache = BoundedCache(ttl_seconds=24 * 60 * 60, maxsize=8)
pitch_response_cache = BoundedCache(ttl_seconds=60 * 60, maxsize=32)


def get_player(player_id: int):
    hit = player_cache.get(player_id, _MISS)
    if hit is not _MISS:
        return hit

    # production에서는 MLB Stats API client 호출
    player = fetch_player_from_source(player_id)

    if player is not None:
        player_cache.set(player_id, player)

    return player
