from blueprints.blue_amari5G import Amari5G
from nfvo import sol006_VNFbuilder
from main import *

db = persistency.DB()
nbiUtil = NbiUtil(username=osm_user, password=osm_passwd, project=osm_proj, osm_ip=osm_ip, osm_port=osm_port)
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
