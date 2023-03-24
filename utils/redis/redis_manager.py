import redis
from redis import Redis
from utils.util import redis_host, redis_port

# Private instance of redis to be distributed on need
redis_instance: Redis = None


def get_redis_instance() -> Redis:
    """
    Return the redis instance, in this way it is unique among all calls.

    @return: The redis instance
    """
    global redis_instance
    if redis_instance is None:
        redis_instance = redis.Redis(host=redis_host, port=redis_port, decode_responses=True, encoding="utf-8")
    return redis_instance
