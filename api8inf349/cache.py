import json
import os

import redis


_redis_client = None


def get_redis():
    global _redis_client
    if _redis_client is None:
        url = os.environ.get("REDIS_URL", "redis://localhost")
        _redis_client = redis.from_url(url)
    return _redis_client


def _key(order_id):
    return f"order:{order_id}"


def cache_order(order_dict):
    r = get_redis()
    order_id = order_dict["order"]["id"]
    r.set(_key(order_id), json.dumps(order_dict))


def get_cached_order(order_id):
    r = get_redis()
    data = r.get(_key(order_id))
    if data is None:
        return None
    return json.loads(data)
