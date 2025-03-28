from nfvcl_core.utils.log import create_logger


class GenericManager:
    def __init__(self):
        self.logger = create_logger(self.__class__.__name__)
        self.logger.debug(f"{self.__class__.__name__} created")
