import logging
from contextlib import contextmanager
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler
from typing import Dict
from redis import Redis
import coloredlogs
import verboselogs
from pathlib import Path

_log_level = logging.DEBUG
# This is thread safe: https://docs.python.org/3/library/contextvars.html
_current_blueprint_id: ContextVar[str | None] = ContextVar("nfvcl_blueprint_id", default=None)
LOG_FILE_PATH = "logs/nfvcl.log"
Path('logs').mkdir(parents=True, exist_ok=True)
Path(LOG_FILE_PATH).touch(exist_ok=True)

# WebSocket handler will be imported dynamically to avoid circular imports
_websocket_handler = None
_websocket_handler_added = False

def set_log_level(level):
    """
    Set the level of the loggers that will be created. Old loggers will have the old value.
    Args:
        level: the level to be set
    """
    global _log_level
    _log_level = level


@contextmanager
def blueprint_log_context(blueprint_id: str | None):
    """
    This is used to give the blueprint_id as context to the logger
    """
    token = _current_blueprint_id.set(blueprint_id)
    try:
        yield
    finally:
        _current_blueprint_id.reset(token)


def add_websocket_handler_to_loggers():
    """
    Add WebSocket handler to all existing loggers when clients connect
    """
    global _websocket_handler, _websocket_handler_added

    if _websocket_handler_added:
        return

    try:
        # Import here to avoid circular imports
        from nfvcl_rest.logs_streamer import WebSocketLoggingHandler, is_websocket_enabled

        if not is_websocket_enabled():
            return

        if _websocket_handler is None:
            _websocket_handler = WebSocketLoggingHandler()
            _websocket_handler.setLevel(_log_level)
            _websocket_handler.setFormatter(formatter)

        # Add to root logger to catch all logs
        root_logger = logging.getLogger(ROOT_LOGGER_NAME)
        if _websocket_handler not in root_logger.handlers:
            root_logger.addHandler(_websocket_handler)
            _websocket_handler_added = True

    except ImportError:
        # WebSocket module not available
        pass


def remove_websocket_handler_from_loggers():
    """
    Remove WebSocket handler from all loggers when no clients are connected
    """
    global _websocket_handler, _websocket_handler_added

    if not _websocket_handler_added or _websocket_handler is None:
        return

    try:
        root_logger = logging.getLogger(ROOT_LOGGER_NAME)
        if _websocket_handler in root_logger.handlers:
            root_logger.removeHandler(_websocket_handler)
            _websocket_handler_added = False
    except Exception:
        pass


coloredlog_format_string = "%(asctime)s [%(name)-20.20s][%(threadName)-10.10s] [%(levelname)8s] [%(blueprintid)s] %(message)s"

level_styles = {
    'trace': {'color': 238, 'faint': True},
    'spam': {'color': 238, 'faint': True},
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


class BlueprintIDFilter(logging.Filter):
    """
    Class used to add a field for the device name to the logger
    """

    def __init__(self, blueprintid=None):
        super().__init__()
        self.blueprintid = blueprintid

    @classmethod
    def install(cls, handler, fmt, blueprintid=None, style=coloredlogs.DEFAULT_FORMAT_STYLE):
        if fmt:
            parser = coloredlogs.FormatStringParser(style=style)
            if not parser.contains_field(fmt, 'blueprintid'):
                return
        handler.addFilter(cls(blueprintid))

    def filter(self, record):
        record.blueprintid = _current_blueprint_id.get() or self.blueprintid
        return 1


logger_dict: Dict[str, verboselogs.VerboseLogger] = {}
handlers_to_add = []


def create_logger(name: str, ov_log_level: int = None, blueprintid='SYSTEM') -> verboselogs.VerboseLogger:
    """
    Creates a logger outputting on: console, redis, and on file.
    In this way, an external entity to the NFVCL is able to observe what is going on.
    The log file allows permanent info in case of failure (NB on next restart the log file is overwritten)

    Args:
        name: The name of the logger to be displayed in logs.
        ov_log_level: Can be used to override global log level
        blueprintid: Blueprint ID to add to the log message

    Returns:

        The created logger
    """
    global logger_dict
    dict_key = f"{name}_{blueprintid}"

    if dict_key in logger_dict:
        return logger_dict[dict_key]

    # If defined use override log level, otherwise the global.
    if ov_log_level is not None:
        local_log_level = ov_log_level
    else:
        local_log_level = _log_level

    logger = verboselogs.VerboseLogger(name)
    logger.parent = logging.getLogger(ROOT_LOGGER_NAME)

    # Adding file handler to post log into file
    # w = every restart log is cleaned

    mod_logger(logger, blueprintid=blueprintid, log_level=local_log_level)

    logger_dict[dict_key] = logger

    return logger


def add_handler_to_all_loggers(handler: logging.Handler):
    """
    Add a handler to all existing loggers.
    This is useful to add a new handler to all loggers without modifying each one.

    Args:
        handler: The logging handler to be added
    """
    global handlers_to_add
    for logger in logger_dict.values():
        if not isinstance(logger, verboselogs.VerboseLogger):
            continue
        if handler not in logger.handlers:
            logger.addHandler(handler)
    handlers_to_add = [handler]

def mod_logger(logger: logging.Logger, blueprintid='SYSTEM', log_level=_log_level, remove_handlers=False, disable_propagate=False):
    """
    This method takes an existing logger and mod it.
    """
    if remove_handlers:
        for old_handler in logger.handlers:
            logger.removeHandler(old_handler)

    if disable_propagate:
        logger.propagate = False

    rotating_log_file_path = Path(LOG_FILE_PATH)
    if not rotating_log_file_path.exists():
        rotating_log_file_path.touch()
    if not rotating_log_file_path.is_file():
        raise FileNotFoundError(f"{LOG_FILE_PATH} is a folder! It should be a file.")
    log_file_handler = RotatingFileHandler(rotating_log_file_path, maxBytes=10000000, backupCount=4)
    log_file_handler.setLevel(log_level)
    log_file_handler.setFormatter(formatter)
    logger.addHandler(log_file_handler)

    # If the config is not yet loaded, we cannot get the Redis instance
    # Workaround for logging before loading config
    # if is_config_loaded():
    #     # Adding Redis handler to output the log to redis through publication
    #     from nfvcl.utils.redis_utils.redis_manager import get_redis_instance
    #     _redis_cli: Redis = get_redis_instance()
    #     redis_handler = RedisLoggingHandler(_redis_cli)
    #     redis_handler.setLevel(log_level)
    #     redis_handler.setFormatter(formatter)
    #     logger.addHandler(redis_handler)

    for handler in handlers_to_add:
        if handler not in logger.handlers:
            logger.addHandler(handler)


    coloredlogs.install(
        level=log_level,
        logger=logger,
        fmt=coloredlog_format_string,
        field_styles=field_styles,
        level_styles=level_styles
    )

    for handler in logger.handlers:
        BlueprintIDFilter.install(
            fmt=coloredlog_format_string,
            handler=handler,
            blueprintid=blueprintid
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
