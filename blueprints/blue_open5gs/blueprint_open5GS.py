from blueprints.blue_amari5G.blueprint_amari5G import Amari5G
from utils import persistency
from nfvo.vnf_manager import sol006_VNFbuilder
from utils.util import create_logger

db = persistency.db()
# create logger
logger = create_logger('open5GS')


class open5GS(Amari5G):
    def set_coreVnfd(self, area: str, vls=None) -> None:
        #FIXME: pass it to KNF
        vnfd = sol006_VNFbuilder({
            'username': 'root',
            'password': 'root',
            'id': self.get_id() + '_open5gs_5gc',
            'name': self.get_id() + '_open5gs_5gc',
            'kdu': [],
            'vdu': [{
                'count': 1,
                'id': 'VM',
                'image': 'amari5GC',
                'vm-flavor': {'memory-mb': '4096', 'storage-gb': '0', 'vcpu-count': '4'},
                'interface': vls,
                'vim-monitoring': True
            }]}, charm_name='flexcharm')
        self.vnfd['core'].append({'id': 'vnfd', 'name': vnfd.get_id(), 'vl': vls})
