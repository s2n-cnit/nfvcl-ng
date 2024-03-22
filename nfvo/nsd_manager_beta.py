from typing import List
from pydantic import TypeAdapter
from typing_extensions import deprecated

from models.blueprint.blueprint_base_model import BlueNSD, BlueDescrNsdItem, BlueVNFD, BlueVNFProfile, BlueDescrVLD, \
    BlueKDUConf, BlueVNFAdditionalParams, BlueDeployConfig, BlueVLD
from models.k8s.k8s_objects import K8sService
from models.osm.osm_vnfi_model import VNFiModelOSM
from models.vim.vim_models import VimNetMap
from models.virtual_link_desc import VirtLinkDescr
from nfvo.osm_nbi_util import get_osm_nbi_utils
from utils import persistency
from utils.log import create_logger
from utils.util import get_nfvcl_config, NFVCLConfigModel

nfvcl_config: NFVCLConfigModel = get_nfvcl_config()
nbiUtil = get_osm_nbi_utils()
db = persistency.DB()

# create logger
logger = create_logger('NSD MANAGER')


def get_nsd_name(nsd_descr: dict) -> str:
    if 'nsd' in nsd_descr:
        return nsd_descr['nsd']['nsd'][0]['name']
    else:
        return nsd_descr['nsd:nsd-catalog']['nsd'][0]['name']

@deprecated("TODO DEPRECATED MESSAGE")
def get_ns_vld_ip(ns_id: str, ns_vlds: list) -> dict:
    """

    Args:
        ns_id: The network service identifier (NSI)
        ns_vlds:

    Returns:

    """
    res = {}
    vnfi_list = nbiUtil.get_vnfi_list(ns_id)
    for vld in ns_vlds:
        res[vld] = get_vnf_ip(vnfi_list, vld)
    return res

def get_ns_vld_model(ns_id: str, ns_vlds_ids: list) -> dict[str, List[VirtLinkDescr]]:
    """
    Retrieve all the virtual link descriptions for a given network service.

    Args:
        ns_id: The network service identifier (NSI)
        ns_vlds_ids: A list of VLD identifiers to be used for retrieving the correct VLD

    Returns:
        A dictionary, indexed by ns_vlds_ids, containing lists of VLD for each vld ID
        {"vld_id1": <VLD_OBJ1>, "vld_id3": <VLD_OBJ3>}
        If a VLD is not found, then the relative key is not present in the dictionary.
    """
    res = {}
    vnfi_list: List[VNFiModelOSM] = nbiUtil.get_vnfi_list_model(ns_id)
    for vld in ns_vlds_ids:
        res[vld] = get_vnf_vld(vnfi_list, vld)
    return res


def get_kdu_services(ns_id: str, kdu_name: str) -> List[K8sService]:
    return TypeAdapter(List[K8sService]).validate_python(nbiUtil.get_kdu_services(ns_id, kdu_name))

@deprecated("TODO DEPRECATED MESSAGE")
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


def get_vnf_vld(vnfi_list: List[VNFiModelOSM], ns_vld_id: str) -> List[VirtLinkDescr]:
    """
    Retrieve a list of VLD associated with the NSD id derived from the VNFi input list.
    Args:
        vnfi_list: The list in witch the VLD are searched
        ns_vld_id: The NS ID used to filter interfaces

    Returns:
        A list containing the VLD of associated with the ns_vld_id
    """
    vld_result_list: List[VirtLinkDescr] = []
    # It looks for a vnfi containing one or more interfaces with the correct vld id
    for vnfi in vnfi_list:
        # Looks for interfaces in each vdu
        for vdu in vnfi.vdur:
            for interface in vdu.interfaces:
                # For each interface it looks for match on vld id
                if interface.ns_vld_id == ns_vld_id:
                    vld = VirtLinkDescr.model_validate({
                        "ns_vld_id": ns_vld_id,
                        "vnfi_id": vnfi.id,
                        "vnfd_name": vnfi.vnfd_ref,
                        "ip": interface.ip_address,
                        "intf_name": interface.name,
                        "external-cp-ref": interface.external_connection_point_ref,
                        "member-vnf-index-ref": vnfi.member_vnf_index_ref,
                        "intf_mac": interface.mac_address,
                        "compute_node": interface.compute_node
                    })
                    vld_result_list.append(vld)

    return vld_result_list


# this class builds nsd from scratch without starting from a template
class Sol006NSDBuilderBeta():
    nsd: BlueDescrNsdItem

    def __init__(self, vnfds: List[BlueVNFD], vim_name: str, nsd_id: str, nsd_type: str, vl_maps: List[VimNetMap], knf_configs: List[BlueKDUConf] | None = None) -> None:
        self.nsd = BlueDescrNsdItem.model_validate({
            'name': nsd_id,
            'id': nsd_id,
            'description': 'Auto built by CNIT S2N NFVCL',
            'df': [
                {
                    'id': 'default-df',
                    'vnf-profile': []
                }
            ],
            'virtual-link-desc': [],
            'version': '3.0',
            'vnfd-id': []
        })

        vnfd: BlueVNFD
        for v_index, vnfd in enumerate(vnfds, start=1):
            self.nsd.vnfd_id.append(vnfd.name)
            vlc = []
            for virtual_link in vnfd.vl:
                vlc.append({
                    'constituent-cpd-id': [
                        {
                            'constituent-cpd-id': virtual_link.vld,
                            'constituent-base-element-id': str(v_index)

                        }
                    ],
                    'virtual-link-profile-id': virtual_link.vld
                })
            self.nsd.df[0].vnf_profile.append(BlueVNFProfile.model_validate(
                {
                    'id': str(v_index),
                    'vnfd-id': vnfd.name,
                    'virtual-link-connectivity': vlc
                })
            )

        self.deploy_config = BlueDeployConfig()

        for vl_map in vl_maps:
            self.nsd.virtual_link_descriptor.append(BlueDescrVLD.model_validate({'id': vl_map.vld, 'mgmt-network': vl_map.mgt}))
            self.deploy_config.vld.append(BlueVLD(name=vl_map.vld, vim_network_name=vl_map.vim_net))

        self.vim = vim_name
        self.type = nsd_type
        if knf_configs:
            self.deploy_config.additionalParamsForVnf = []
            for knf_config in knf_configs:
                # TODO allow multiple vnf per ns
                self.deploy_config.additionalParamsForVnf.append(
                    BlueVNFAdditionalParams(
                        member_vnf_index=str(knf_configs.index(knf_config) + 1),
                        additionalParamsForKdu=[knf_config]
                    )
                )
            logger.debug("Deployment config for kdu: {}".format(self.deploy_config))

    def get_nsd(self) -> BlueNSD:
        res = {'status': 'day0', 'vim': self.vim, 'type': self.type, 'descr': {'nsd': {
            'nsd': [self.nsd.model_dump(exclude_none=True, by_alias=True)]}},
               'deploy_config': self.deploy_config}
        # TODO avoid double conversion of self.nsd
        return BlueNSD.model_validate(res)
