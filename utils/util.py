import logging
import string
import random
import yaml

with open("config.yaml", 'r') as stream:
    try:
        nfvcl_conf = yaml.safe_load(stream)
    except yaml.YAMLError as exc:
        print(exc)

    # Parsing the config file
    try:
        nfvcl_ip = nfvcl_conf['nfvcl']['ip']
        nfvcl_port = str(nfvcl_conf['nfvcl']['port'])

        osm_ip = nfvcl_conf['osm']['host']
        osm_port = str(nfvcl_conf['osm']['port'])
        osm_user = nfvcl_conf['osm']['username']
        osm_passwd = nfvcl_conf['osm']['password']
        osm_proj = nfvcl_conf['osm']['project']
        if 'version' in nfvcl_conf['osm']:
            if nfvcl_conf['osm']['version'] > 8:
                sol006 = True

        mongodb_host = nfvcl_conf['mongodb']['host']
        mongodb_port = str(nfvcl_conf['mongodb']['port'])
        mongodb_db = nfvcl_conf['mongodb']['db']
        redis_host = nfvcl_conf['redis']['host']
        redis_port = str(nfvcl_conf['redis']['port'])
    except Exception as exception:
        print('exception in the configuration file parsing: {}'.format(str(exception)))


def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))


def create_logger(name: str) -> logging.getLogger:
    # create logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    # create console handler and set level to debug
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    # create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    # add formatter to ch
    ch.setFormatter(formatter)
    # add ch to logger
    logger.addHandler(ch)
    return logger


# Class decorator for locking methods
def obj_multiprocess_lock(func):
    def wrapper(self, *args, **kwargs):
        print("acquiring lock")
        self.lock.acquire()
        print("acquired lock")

        r = func(self, *args, **kwargs)

        print("releasing lock")
        self.lock.release()
        print("released lock")
        return r

    return wrapper


def deprecated(func):
    """
    Deprecated decorator. When a function is tagged with this decorator, every time the function is called, it prints
    that the function is deprecated.
    """
    def wrapper(*args, **kwargs):
        print('Function', func.__name__, 'is deprecated.')
        return func(*args, **kwargs)
    return wrapper