from utils import persistency
from nfvo import NbiUtil
from utils.util import *
import typing

logger = create_logger('PNF-Manager')

nbiUtil = NbiUtil(username=osm_user, password=osm_passwd, project=osm_proj, osm_ip=osm_ip, osm_port=osm_port)
db = persistency.DB()


class PNFmanager:
    def create(self, msg: dict) -> None:
        logger.debug(msg)
        data = msg
        try:
            #if data['type'] not in ['gnb', 'enb', 'bs']:
            #    logger.error('pnf type not supported')
            #    return
            pdu_list = nbiUtil.get_pdu_list()
            pdu = None
            if pdu_list:
                for item in pdu_list:
                    logger.debug('now analyzing ' + item['name'])
                    logger.debug(item)
                    if item['name'] == data['name']:
                        logger.error('PDU already existing')
                        pdu = item
                        #checking if IN_USE
                        break
            if pdu is not None:
                logger.error('pdu already existing. aborting')
            else:
                #create mongo item
                res = nbiUtil.add_pdu(msg)
                logger.info(res)

        except ValueError as err:
            logger.error(err)
            raise ValueError('error in creating PDU')


    def get(self, name: typing.Optional[str] = None):

        pdu_list = nbiUtil.get_pdu_list()
        if pdu_list:
            if name:
                for item in pdu_list:
                    logger.debug('now analyzing pdu ' + item['name'])
                    if item['name'] == name:
                        return item
            else:
                return pdu_list
        return None

    def delete(self, name):
        pdu = self.get(name)
        result = nbiUtil.delete_pdu(pdu['_id'])
        return result
