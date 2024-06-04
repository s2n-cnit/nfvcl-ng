from nfvcl.blueprints.blue_amari5G import Amari5G
from nfvcl.nfvo import sol006_VNFbuilder
from nfvcl.main import *
from nfvcl.utils.log import create_logger

db = persistency.DB()
nbiUtil = get_osm_nbi_utils()
# create logger
logger = create_logger('open5GS')


class open5GS(Amari5G):
    def set_core_vnfd(self, area: str, vls=None) -> None:

        vnfd = sol006_VNFbuilder(self.nbiutil, self.db, {
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
