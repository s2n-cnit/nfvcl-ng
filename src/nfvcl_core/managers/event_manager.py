from functools import partial
from threading import Thread

import blinker
from pydantic import ValidationError
from redis import Redis

from nfvcl_core.managers import TaskManager
from nfvcl_core.managers.generic_manager import GenericManager
from nfvcl_core.models.event import Event
from nfvcl_core.models.event_types import NFVCLEventTopics, NFVCLEventType
from nfvcl_core.models.task import NFVCLTask


class EventManager(GenericManager):
    def __init__(self, task_manager: TaskManager, redis_host: str, redis_port: int):
        super().__init__()
        self._task_manager = task_manager
        self.redis_instance = Redis(host=redis_host, port=redis_port, decode_responses=True, encoding="utf-8")
        self.publish_to_redis = True
        self.sub_to_redis = True
        self.subscribe_all_debug()

        self.redis_subscriber = self.redis_instance.pubsub()
        self.redis_subscriber.subscribe(NFVCLEventTopics.K8S_MANAGEMENT_TOPIC)

        self.redis_subscriber_thread_running = True
        self.redis_subscriber_thread = Thread(target=self.redis_sub_loop, daemon=True, name="RedisSubscriber")
        self.redis_subscriber_thread.start()


    def redis_sub_loop(self):
        # Alerting if there are no subscriptions
        if(len(self.redis_subscriber.channels)) <= 0:
            self.logger.warning("There are NO active subscriptions to events!!!")

        for message in self.redis_subscriber.listen():
            if not self.redis_subscriber_thread_running:
                break
            data = message['data']
            if message['type'] == 'subscribe':
                self.logger.info(f"Successfully subscribed to redis topic: {message['channel']}")
            elif message['type'] == 'unsubscribe':
                self.logger.info(f"Successfully unsubscribed from redis topic: {message['channel']}")
            elif message['type'] == 'message':
                try:
                    event = Event.model_validate(data)
                    self.fire_event(message['channel'], NFVCLEventType(event.operation), event.data, from_redis=True)
                except ValidationError as val_err:
                    msg_err = "Received model is impossible to validate."
                    self.logger.error(msg_err)
                    raise val_err
            else:
                msg_err = "Redis message type not recognized."
                self.logger.error(msg_err)
                raise ValidationError(msg_err)


    def debug_callback(self, topic, **kwargs):
        self.logger.verbose(f"** EVENT ** -> Topic: {topic}, Kwargs: {kwargs}")

    def subscribe_all_debug(self):
        self.logger.debug("Subscribing to all topics for debug")
        # Iterate over all the topics and events
        for topic in NFVCLEventTopics:
            self.logger.debug(f"Subscribing to {topic}")
            self.subscribe_topic(topic, partial(self.debug_callback, topic), run_async=False)

    def fire_event(self, topic: NFVCLEventTopics, event: NFVCLEventType, data=None, from_redis=False):
        signal_topic = blinker.signal(topic.value)
        signal_event = blinker.signal(f"{topic.value}_{event.value}")
        signal_topic.send(event_type=event.value, data=data)
        signal_event.send(data=data)

        if not from_redis and self.publish_to_redis:
            event: Event = Event(operation=event.value, data=data if isinstance(data, dict) else data.model_dump())
            self.redis_instance.publish(topic.value, event.model_dump_json())

    def subscribe_event(self, topic: NFVCLEventTopics, event: NFVCLEventType, callback: callable, run_async=False):
        signal_event = blinker.signal(f"{topic.value}_{event.value}")

        def callback_wrapper(sender, **kwargs):
            try:
                if run_async:
                    self._task_manager.add_task(NFVCLTask(callback, None, **kwargs))
                else:
                    callback(**kwargs)
            except Exception as e:
                self.logger.error(f"Error in callback {callback} for event {event} in topic {topic}: {e}")

        signal_event.connect(callback_wrapper, weak=False)

    def subscribe_topic(self, topic: NFVCLEventTopics, callback: callable, run_async=False):
        signal_topic = blinker.signal(topic.value)

        def callback_wrapper(sender, **kwargs):
            try:
                if run_async:
                    self._task_manager.add_task(NFVCLTask(callback, None, **kwargs))
                else:
                    callback(**kwargs)
            except Exception as e:
                self.logger.error(f"Error in callback {callback} for topic {topic}: {e}")

        signal_topic.connect(callback_wrapper, weak=False)
