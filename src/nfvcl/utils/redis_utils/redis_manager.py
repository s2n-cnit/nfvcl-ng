import redis
from redis import Redis
from nfvcl.models.event import Event
from nfvcl.utils.util import get_nfvcl_config

# Private instance of redis to be distributed on need
redis_instance: Redis = None
nfvcl_config = get_nfvcl_config()


def get_redis_instance() -> Redis:
    """
    Return the redis instance, in this way it is unique among all calls.

    @return: The redis instance
    """
    global redis_instance
    if redis_instance is None:
        redis_instance = redis.Redis(host=nfvcl_config.redis.host, port=nfvcl_config.redis.port, decode_responses=True,
                                     encoding="utf-8")
    return redis_instance


def trigger_redis_event(redis_cli: Redis, topic: str, event: Event):
    """
    Send an event, together with the data that have been updated, to REDIS.

    Args:
        redis_cli: redis client instance
        topic: the topic where the event is published
        event: the event to be triggered
    """
    redis_cli.publish(topic, event.model_dump_json())
