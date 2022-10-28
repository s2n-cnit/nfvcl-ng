from configurators.flex_configurator import Configurator_Flex
import logging
#import os, sys, yaml

# create logger
logger = logging.getLogger('Configurator_DockerNode')
logger.setLevel(logging.INFO)
# create console handler and set level to debug
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
# create formatter
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# add formatter to ch
ch.setFormatter(formatter)
# add ch to logger
logger.addHandler(ch)


class Configurator_DockerNode(Configurator_Flex):
    def __init__(self, nsd_id, m_id, blue_id, args):
        self.type = "oaienb_1nic"
        super(Configurator_DockerNode, self).__init__(nsd_id, m_id, blue_id)
        logger.info("Configurator_DockerNode allocated")

    def dump(self):
        return super(Configurator_DockerNode, self).dump()
