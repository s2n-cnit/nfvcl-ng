import redis
from redis import Redis
from nfvcl.models.event import Event
from nfvcl.utils.redis_utils.event_types import NFVCLEventType
from nfvcl.utils.util import get_nfvcl_config

# Private instance of redis to be distributed on need
redis_instance: Redis | None = None
nfvcl_config = get_nfvcl_config()


def get_redis_instance() -> Redis:
    """
    Return the redis instance, in this way it is unique among all calls.

    Returns:
        The redis instance
    """
    global redis_instance
    if redis_instance is None:
        redis_instance = redis.Redis(host=nfvcl_config.redis.host, port=nfvcl_config.redis.port, decode_responses=True, encoding="utf-8")
    return redis_instance


def trigger_redis_event(topic: str, event_type: NFVCLEventType, data: dict):
    """
    Send an event, together with the data that have been updated, to REDIS.

    Args:
        topic: the topic where the event is published
        event_type (NFVCLEventType): the type of event
        data: the data that describe the type of event
    """
    redis_cli = get_redis_instance()
    event: Event = Event(operation=event_type.value, data=data)
    redis_cli.publish(topic, event.model_dump_json())
