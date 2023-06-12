import logging

from utils.redis.redis_manager import get_redis_instance
from redis import Redis

redis_cli: Redis = get_redis_instance()


def create_logger(name: str) -> logging.Logger:
    """
    Creates a logger that is outputting on: console, redis and on file.
    In this way an external entity to the NFVCL is able to observe what is going on.
    The log file allow permanent info in case of failure (NB on next restart the log file is overwritten)

    Args:

        name: The name of the logger to be displayed in logs.

    Returns:

        The created logger
    """
    # create logger
    logger = logging.getLogger(name)
    logger.propagate = False
    logger.setLevel(logging.DEBUG)

    # create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # create console handler and set level to debug
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    # add formatter to console handler
    ch.setFormatter(formatter)
    # add console handler to logger
    logger.addHandler(ch)

    # Adding file handler to post log into file
    # w = every restart log is cleaned
    log_file_handler = logging.FileHandler("nfvcl.log", mode="w")
    log_file_handler.setLevel(logging.DEBUG)
    log_file_handler.setFormatter(formatter)
    logger.addHandler(log_file_handler)

    # Adding Redis handler to output the log to redis through publish
    redis_handler = RedisLoggingHandler(redis_cli)
    redis_handler.setLevel(logging.DEBUG)
    redis_handler.setFormatter(formatter)
    logger.addHandler(redis_handler)
    return logger


def mod_logger(logger: logging.Logger) -> logging.Logger:
    """
    This method takes an existing logger and mod it.
    Delete existing handlers and add custom ones.

    Args:
        logger: the logger to be erased and replaced.

    Returns:
        the new logger
    """
    # Deleting previous handlers
    logger.handlers.clear()

    # The method create logger will take the same logger and add custom handlers to it
    return create_logger(logger.name)

class RedisLoggingHandler(logging.Handler):
    """
    This custom handler allow to output logs on redis. In this way an external entity to the NFVCL is able to
    observe what is going on, without need to connect at the NFVCL machine.
    """
    def __init__(self, redis_instance: Redis, *args, **kwargs):
        """
        Args:
            redis_instance: the redis instance, where to publish logs.
        """
        super().__init__(*args, **kwargs)
        self.redis_instance = redis_instance

    def emit(self, record):
        """
        Format and publish the record on redis

        Args:
            record: the record to be published
        """
        s = self.format(record)
        self.redis_instance.publish('NFVCL_LOG', s)
