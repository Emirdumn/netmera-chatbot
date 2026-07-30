"""Redis tabanli soru-cevap cache'i.

Redis erisilemez olursa sistem CRASH ETMEMELI — sadece cache'siz devam
etmeli. Bu yuzden her cagri kisa timeout'lu ve try/except ile sarilmis;
baglanti hatasi bir kere loglanir (spam edilmez), sonrasinda sessizce
None/no-op donulur.
"""
import logging

import redis

from config.settings import REDIS_URL

logger = logging.getLogger(__name__)

_client = None
_warned = False


def _get_client():
    global _client
    if _client is None:
        _client = redis.Redis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
        )
    return _client


def _warn_once(exc):
    global _warned
    if not _warned:
        logger.warning("Redis erisilemedi, bu surec icin cache devre disi: %s", exc)
        _warned = True


def cache_get(key: str) -> str | None:
    try:
        return _get_client().get(key)
    except redis.RedisError as exc:
        _warn_once(exc)
        return None


def cache_set(key: str, value: str, ttl: int) -> None:
    try:
        _get_client().set(key, value, ex=ttl)
    except redis.RedisError as exc:
        _warn_once(exc)
