from functools import wraps
from inspect import signature
from typing import Any, Callable

from utils.util import logger


def obj_multiprocess_lock(func):
    """
    Class decorator for locking methods that edit topology information
    Semaphore for topology. Locks the topology such that only ONE operation is made at the same time.
    """
    def wrapper(self, *args, **kwargs):
        logger.debug("Acquiring lock")
        self.lock.acquire()
        logger.debug("Acquired lock")

        # In case of crash, we still need to unlock the semaphore -> TRY
        try:
            #
            response = func(self, *args, **kwargs)
            logger.debug("Releasing lock")
            self.lock.release()
            logger.debug("Released lock")
            return response
        except Exception as excep:
            # In case of crash, we still need to unlock the semaphore
            self.lock.release()
            raise excep

    return wrapper


def change_arg_type(model: Any):
    def decorator(function):

        @wraps(function)
        def wrapper(*args, **kwargs):
            return function(*args, **kwargs)

        sig = signature(function)
        param = sig.parameters['model']
        param._annotation = model

        wrapper.__signature__ = sig

        return wrapper

    return decorator
