from nfvo import NbiUtil
from utils import persistency
from utils.util import *

sol006 = True
nbiUtil = NbiUtil(username=osm_user, password=osm_passwd, project=osm_proj, osm_ip=osm_ip, osm_port=osm_port)
db = persistency.DB()

# create logger
logger = create_logger('nsd_manager')


def get_nsd_name(nsd_descr: dict) -> str:
    if 'nsd' in nsd_descr:
        return nsd_descr['nsd']['nsd'][0]['name']
    else:
        return nsd_descr['nsd:nsd-catalog']['nsd'][0]['name']


def get_ns_vld_ip(ns_id: str, ns_vlds: list) -> dict:
    res = {}
    vnfi_list = nbiUtil.get_vnfi_list(ns_id)
    for vld in ns_vlds:
        res[vld] = get_vnf_ip(vnfi_list, vld)
    return res

def get_kdu_services(ns_id: str, kdu_name: str) -> list:
    return nbiUtil.get_kdu_ips(ns_id, kdu_name)

def get_vnf_ip(vnfi_list: list, ns_vld_id: str) -> list:
    addr_list = []
    # logger.debug(vnfi_list)
    for vnfi in vnfi_list:
        # logger.debug(vnfi)
        for r in vnfi['vdur']:
            for i in r['interfaces']:
                # logger.error(i['ns-vld-id'])
                if i['ns-vld-id'] == ns_vld_id:
                    addr_item = {
                        "ns_vld_id": ns_vld_id,
                        "vnfi_id": vnfi['id'],
                        "vnfd_name": vnfi['vnfd-ref'],
                        "ip": i['ip-address'],
                        "intf_name": i['name'],
                        "external-cp-ref": i['external-connection-point-ref'],
                        "member-vnf-index-ref": vnfi['member-vnf-index-ref']
                    }
                    if "mac-address" in i:
                        addr_item["intf_mac"] = i["mac-address"]
                    if "compute_node" in i:
                        addr_item["compute_node"] = i["compute_node"]
                    addr_list.append(addr_item)
    return addr_list


# this class builds nsd from scratch without starting from a template
class sol006_NSD_builder():
    def __init__(self, vnfds: list, vim_name: str, param: dict, vl_map: list, knf_configs=None) -> None:
        self.n = {
            'name': param['name'],
            'id': param['id'],
            'description': 'autobuilt by CNIT S2N NFVCL',
            'df': [
                {
                    'id': 'default-df',
                    'vnf-profile': []
                }
            ],
            'virtual-link-desc': [],
            'version': '3.0',
            'vnfd-id': []
        }

        for v_index, v in enumerate(vnfds, start=1):
            self.n['vnfd-id'].append(v['name'])  # name is vnfd.get_id()
            vlc = []
            for vl in v['vl']:
                vlc.append({
                    'constituent-cpd-id': [
                        {
                            'constituent-cpd-id': vl['vld'],
                            'constituent-base-element-id': str(v_index)

                        }
                    ],
                    'virtual-link-profile-id': vl['vld']
                })
            self.n['df'][0]['vnf-profile'].append(
                {
                    'id': str(v_index),
                    'vnfd-id': v['name'],
                    'virtual-link-connectivity': vlc
                }
            )
        for vl in vl_map:
            self.n['virtual-link-desc'].append({'id': vl['vld'], 'mgmt-network': vl['mgt']})

        self.vim = vim_name
        self.type = param['type']

        self.deploy_config = {'vld': []}
        for m in vl_map:
            self.deploy_config['vld'].append({'name': m['vld'], 'vim-network-name': m['vim_net']})
        if knf_configs is not None and type(knf_configs) is list:
            self.deploy_config["additionalParamsForVnf"] = []
            for knf in knf_configs:
                 self.deploy_config["additionalParamsForVnf"].append({
                     #"member-vnf-index": knf['vnf_id'],
                     "member-vnf-index": "1",
                     "additionalParamsForKdu": knf['kdu_confs']
                 })
            logger.debug("deployment config for kdu: {}".format(self.deploy_config))

    def get_nsd(self) -> dict:
        res = {'status': 'day0', 'vim': self.vim, 'type': self.type, 'descr': {'nsd': {'nsd': [self.n]}},
               'deploy_config': self.deploy_config}
        return res


# this class builds nsds starting from a template on mongoDB
class NSDmanager():
    def __init__(self, blueprint, template, vnfds, vim, param, vl_map):
        self.findNsdTemplate(template)
        self.updateVnfdNames(vnfds)
        self.mapVLinks(vl_map)
        self.n['name'] = param['name']
        self.n['id'] = param['id']
        self.vim = vim
        self.template = template

    def findNsdTemplate(self, template: dict) -> None:
        if sol006:
            collection = "nsd_templates_sol006"
        else:
            collection = "nsd_templates"

        templates = db.find_DB(collection, {'category': template['category'], 'type': template['type']})
        n_ = next((item for item in templates if
                   (set(template['flavors']['include']) <= set(item['flavors'])) and not bool(
                       set(template['flavors']['exclude']) & set(item['flavors']))), None)
        if n_ is None:
            raise ValueError('NSD template not found in the catalogue')
        self.n = n_['descriptor']

    def updateVnfdNames(self, vnfd_names: list) -> None:
        if sol006:
            self.updateVnfdNames_sol006(vnfd_names)
        else:
            self.updateVnfdNames_legacy(vnfd_names)

    def updateVnfdNames_sol006(self, vnfd_names: list) -> None:
        for v in vnfd_names:
            # check if we have all the VNFDs that the template needs
            logger.info(vnfd_names)
            names_to_replace = self.n['vnfd-id'][:]
            for v in vnfd_names:
                # if v is not in names_to_replace, a ValueError is raised
                names_to_replace.remove(v['id'])
            if names_to_replace:
                # logger.error(len(names_to_replace))
                # logger.error(names_to_replace)
                raise ValueError(
                    "Missing vnfds in building ns descriptor: " + ' '.join([str(elem) for elem in names_to_replace]))

            self.n['vnfd-id'] = []
            for v in vnfd_names:
                self.n['vnfd-id'].append(v['name'])
            for df in self.n['df']:
                for vp in df['vnf-profile']:
                    if vp['vnfd-id'] == v['id']:
                        vp['vnfd-id'] = v['name']

    def updateVnfdNames_legacy(self, vnfd_names: list) -> None:
        for v in vnfd_names:
            for ref in self.n['constituent-vnfd']:
                if ref['vnfd-id-ref'] == v['id']:
                    ref['vnfd-id-ref'] = v['name']
            for link in self.n['vld']:
                for ref in link['vnfd-connection-point-ref']:
                    if ref['vnfd-id-ref'] == v['id']:
                        ref['vnfd-id-ref'] = v['name']

    def mapVLinks(self, vl_map: list) -> None:
        # vl_map: [{id: vl1, net_name: vim3_net5_name}, ...]
        if sol006 is True:
            # nsd now does not allow specifying vim network names.
            # It should be done by setting additional properties to the instantiation message
            # {vld: [ {name: mgmtnet, vim-network-name: mngn-vnf-os} ] }
            self.deploy_config = {'vld': []}
            for m in vl_map:
                self.deploy_config['vld'].append({'name': m['vld'], 'vim-network-name': m['vim_net']})
        else:
            for m in vl_map:
                vl = next((item for item in self.n['vld'] if item == m['vld']), None)
                if vl is None:
                    raise ValueError('Virtual link with id ' + m['vld'] + ' not found')
                    # continue
                vl['vim-network-name'] = m['vim_net']

    def get_nsd(self) -> dict:
        res = {
            'status': 'day0',
            'vim': self.vim,
            'type': self.template['type']
        }
        if sol006:
            res['descr'] = {'nsd': {'nsd': [self.n]}}
            res['deploy_config'] = self.deploy_config
        else:
            res['descr'] = {'nsd:nsd-catalog': {'nsd': [self.n]}}

        return res
