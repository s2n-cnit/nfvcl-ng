import logging
from logging.handlers import RotatingFileHandler
from redis import Redis
import coloredlogs
import verboselogs

from utils.util import is_config_loaded

_log_level = logging.DEBUG


def set_log_level(level):
    """
    Set the level of the loggers that will be created. Old loggers will have the old value.
    Args:
        level: the level to be set
    """
    global _log_level
    _log_level = level


coloredlog_format_string = "%(asctime)s [%(name)-20.20s][%(threadName)-10.10s] [%(levelname)8s] %(message)s"

level_styles = {
    'spam': {'color': 'green', 'faint': True},
    'debug': {'color': 241},
    'verbose': {'color': 'blue'},
    'info': {},
    'notice': {'color': 'magenta'},
    'warning': {'color': 'yellow'},
    'success': {'color': 'green', 'bold': True},
    'error': {'color': 'red'},
    'critical': {'color': 'red', 'bold': True}
}

field_styles = {
    'asctime': {'color': 247},
    'hostname': {'color': 'magenta'},
    'levelname': {'color': 'cyan', 'bold': True},
    'name': {'color': 33},
    'programname': {'color': 'cyan'},
    'username': {'color': 'yellow'},
    'devicename': {'color': 34}
}
coloredlog_formatter = coloredlogs.ColoredFormatter(
    fmt=coloredlog_format_string,
    field_styles=field_styles,
    level_styles=level_styles
)

ROOT_LOGGER_NAME = "RootLogger"
formatter = logging.Formatter(coloredlog_format_string)


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
    logger = verboselogs.VerboseLogger(name)
    logger.parent = logging.getLogger(ROOT_LOGGER_NAME)

    # Adding file handler to post log into file
    # w = every restart log is cleaned
    log_file_handler = RotatingFileHandler("logs/nfvcl.log", maxBytes=10000000, backupCount=4)
    log_file_handler.setLevel(_log_level)
    log_file_handler.setFormatter(formatter)
    logger.addHandler(log_file_handler)

    # If the config is not yet loaded we cannot get the Redis instance
    # Workaround for logging before loading config
    if is_config_loaded():
        # Adding Redis handler to output the log to redis through publish
        from utils.redis_utils.redis_manager import get_redis_instance
        _redis_cli: Redis = get_redis_instance()
        redis_handler = RedisLoggingHandler(_redis_cli)
        redis_handler.setLevel(_log_level)
        redis_handler.setFormatter(formatter)
        logger.addHandler(redis_handler)

    coloredlogs.install(
        level=_log_level,
        logger=logger,
        fmt=coloredlog_format_string,
        field_styles=field_styles,
        level_styles=level_styles
    )

    return logger


def mod_logger(logger: logging.Logger):
    """
    This method takes an existing logger and mod it.
    """
    coloredlogs.install(
        level=_log_level,
        logger=logger,
        fmt=coloredlog_format_string,
        field_styles=field_styles,
        level_styles=level_styles
    )


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
