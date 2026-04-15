from rq import Queue

from api8inf349.cache import get_redis


_queue = None


def get_queue():
    global _queue
    if _queue is None:
        _queue = Queue(connection=get_redis())
    return _queue
