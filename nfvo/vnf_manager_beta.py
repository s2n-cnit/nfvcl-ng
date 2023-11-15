import os
import shutil
import tarfile
from typing import Union, List
from multiprocessing import RLock
import yaml

from models.blueprint.blueprint_base_model import BlueVNFD
from models.charm_models import CharmPrimitive, CharmExecEnviron, CharmDay12, LCMOperationConfig
from models.network import PduModel, PduInterface
from models.vim.vim_models import VirtualNetworkFunctionDescriptor, PDUDeploymentUnit, VimLink, VimNetMap
from models.vnfd_model import VNFSol006Descriptor, VDUSol006Descriptor, VirtualComputeDescr006, VirtualStorageDescr006, \
    InstantiationLevel, ExtCPD, IntCPD, KDU, DF, VDULevel, VDUProfile, KDUcluster
from topology.topology import Topology
from nfvo.osm_nbi_util import NbiUtil, get_osm_nbi_utils
from nfvo.pnf_manager import PNFmanager
from utils.persistency import DB
from utils.log import create_logger
from utils.util import copytree

logger = create_logger('vnfd_manager')

osm_nbi_util: NbiUtil = get_osm_nbi_utils()
db: DB = DB()

FLEX_CHARM = 'flexcharm'
FLEX_CHARM2 = 'flexcharm2'
FLEX_CHARM_VYOS = 'flexcharmvyos'
HELM_FLEX_VNFM = 'helmflexvnfm'
SUPPORTED_CHART_TYPES = [FLEX_CHARM, FLEX_CHARM2, FLEX_CHARM_VYOS, HELM_FLEX_VNFM]
JUJU_CHARM_TYPES = [FLEX_CHARM, FLEX_CHARM2, FLEX_CHARM_VYOS]
VNF_BASE_PATH = '/tmp/vnf_packages'
VNF_BASE_PATH_PACKAGE = '/tmp/vnf_packages/{}_vnfd'


class Sol006VnfdBuilderBeta:
    vnfd_model: VNFSol006Descriptor
    received_vdu_links: List[VimLink]
    received_kdu_links: List[VimNetMap]
    type: str

    def __init__(self, vnf_model_data: VirtualNetworkFunctionDescriptor, hemlflexcharm: bool = False,
                 cloud_init: bool = False, adapt_interfaces=False) -> None:
        self.cloud_init = cloud_init
        self.adapt_interfaces = adapt_interfaces

        if len(vnf_model_data.vdu) > 0:
            # Saving VDU links for usage in the descriptor. All vdu should have the same links soo we save the first one.
            self.received_vdu_links = vnf_model_data.vdu[0].interface
            vim_net_map = next(item for item in vnf_model_data.vdu[0].interface if item.mgt)
            vnf_model_data.mgmt_cp = vim_net_map.vld

        elif len(vnf_model_data.kdu) > 0:
            self.received_kdu_links = vnf_model_data.kdu[0].interface
            vim_net_map = next(item for item in vnf_model_data.kdu[0].interface if item.mgt)
            vnf_model_data.mgmt_cp = vim_net_map.vld

        elif len(vnf_model_data.pdu) > 0:
            vim_net_map = next(item for item in vnf_model_data.pdu[0].interface if item.mgt)
            vnf_model_data.mgmt_cp = vim_net_map.vld

        else:
            raise ValueError('Cannot find VDUs, KDUs or PDUs in vnf_data!!')

        self.create_sol006_descriptor_model(vnf_model_data)
        if hemlflexcharm:
            self.add_charm(vnf_model_data)
        self.create_package(vnf_model_data)

    def get_id(self) -> str:
        return self.vnfd_model.id

    def get_vnf_blue_descr_only_vdu(self) -> BlueVNFD:
        blue_vnfd = BlueVNFD.model_validate({'id': 'vnfd', 'name': self.get_id()})
        blue_vnfd.vl = self.received_vdu_links
        return blue_vnfd

    def get_vnf_blue_descr_only_kdu(self) -> BlueVNFD:
        blue_vnfd = BlueVNFD.model_validate({'id': 'vnfd', 'name': self.get_id()})
        blue_vnfd.vl = self.received_kdu_links
        return blue_vnfd

    def create_sol006_descriptor_model(self, vnf: VirtualNetworkFunctionDescriptor):
        self.vnfd_model = VNFSol006Descriptor.model_validate({
            'id': vnf.id,
            'product-name': vnf.name,
            'mgmt-cp': vnf.mgmt_cp
        })

        if len(vnf.vdu) > 0:
            self.type = 'vnfd'
            for received_vdu in vnf.vdu:
                vdu_006 = VDUSol006Descriptor.model_validate({
                    'id': received_vdu.id,
                    'name': received_vdu.id,
                    'int-cpd': [self.add_vdu_cp_model(interface, received_vdu.id) for interface in
                                received_vdu.interface],
                    'sw-image-desc': received_vdu.image,
                    'virtual-compute-desc': received_vdu.id + '_compute_desc',
                    'virtual-storage-desc': [received_vdu.id + '_storage_desc']
                })

                if received_vdu.vim_monitoring:
                    vdu_006.monitoring_parameter = self.add_vim_monitoring()

                # Adding sw-image-desc to object, if not already present.
                image_ref = next(
                    (item for item in self.vnfd_model.sw_image_desc if item['name'] == received_vdu.image), None)
                if image_ref is None:
                    self.vnfd_model.sw_image_desc.append({'id': received_vdu.image, 'image': received_vdu.image,
                                                          'name': received_vdu.image})

                self.vnfd_model.virtual_compute_desc.append(VirtualComputeDescr006.model_validate({
                    'id': received_vdu.id + '_compute_desc',
                    'virtual-cpu': {'num-virtual-cpu': int(received_vdu.vm_flavor.vcpu_count)},
                    'virtual-memory': {'size': str(int(received_vdu.vm_flavor.memory_mb) / 1024)}
                }))

                # Adding storage desc
                self.vnfd_model.virtual_storage_desc.append(VirtualStorageDescr006.model_validate(
                    {'id': received_vdu.id + '_storage_desc',
                     'size-of-storage': int(received_vdu.vm_flavor.storage_gb)}))

                self.vnfd_model.vdu.append(vdu_006)
                # adding deployment flavor
                self.add_vdu_df_model('default-df', 'default-instantiation-level', received_vdu.id)

        if len(vnf.pdu) > 0:
            self.type = 'pnfd'
            for received_pdu in vnf.pdu:
                pdu = self.manage_pdu_model(received_pdu)
                # update the username and password
                vnf.update({'username': pdu.user, 'password': pdu.passwd})
                # now prepare the descriptor
                vdu_obj: VDUSol006Descriptor = VDUSol006Descriptor.model_validate({
                    'id': pdu.name,
                    'name': pdu.name,
                    'int-cpd': [self.add_vdu_cp_model(interface, pdu.name, define_type=False) for interface in
                                pdu.interface],
                    'pdu-type': pdu.type
                })
                self.vnfd_model.vdu.append(vdu_obj)
                # adding deployment flavor
                self.add_vdu_df_model('default-df', 'default-instantiation-level', received_pdu['id'])

        if len(vnf.kdu) > 0:
            self.type = 'knfd'
            for received_kdu in vnf.kdu:
                self.vnfd_model.kdu.append(KDU.model_validate({'name': received_kdu.name, 'helm-chart':
                    received_kdu.helm_chart}))

                kdu_interface: VimNetMap
                for kdu_interface in received_kdu.interface:
                    if self.vnfd_model.k8s_cluster is None:
                        self.vnfd_model.k8s_cluster = KDUcluster()

                    self.vnfd_model.k8s_cluster.nets.append({'id': kdu_interface.k8s_cluster_net})

                    self.vnfd_model.ext_cpd.append(ExtCPD.model_validate({'id': kdu_interface.vld,
                                                                          'k8s-cluster-net': kdu_interface.k8s_cluster_net}))

                    if kdu_interface.mgt:
                        self.vnfd_model.mgmt_cp = kdu_interface.vld

    def add_vim_monitoring(self) -> list:
        return [
            {'id': 'vdu_cpu_util', 'name': 'vdu_cpu_util', 'performance-metric': 'cpu_utilization'},
            {'id': 'vdu_avg_mem_util', 'name': 'vdu_avg_mem_utill', 'performance-metric': 'average_memory_utilization'},
            {'id': 'vdu_tx_pkts', 'name': 'vdu_tx_pkts', 'performance-metric': 'packets_sent'},
            {'id': 'vdu_rx_pkts', 'name': 'vdu_rx_pkts', 'performance-metric': 'packets_received'},
            {'id': 'vdu_disk_read_ops', 'name': 'vdu_disk_read_ops', 'performance-metric': 'disk_read_ops'},
            {'id': 'vdu_disk_write_ops', 'name': 'vdu_disk_write_ops', 'performance-metric': 'disk_write_ops'},
            {'id': 'vdu_disk_read_bytes', 'name': 'vdu_disk_read_bytes', 'performance-metric': 'disk_read_bytes'},
            {'id': 'vdu_disk_write_bytes', 'name': 'vdu_disk_write_bytes', 'performance-metric': 'disk_write_bytes'},
            {'id': 'vdu_rx_drop_pkts', 'name': 'vdu_rx_drop_pkts', 'performance-metric': 'packets_in_dropped'},
            {'id': 'vdu_tx_drop_pkts', 'name': 'vdu_tx_drop_pkts', 'performance-metric': 'packets_out_dropped'},
        ]

    def add_vdu_cp_model(self, pdu_interface: Union[VimLink, PduInterface], vdu_id: str,
                         define_type: bool = True) -> IntCPD:
        # Mapping ex-cp to int-cp and saving it in the model
        self.vnfd_model.ext_cpd.append(ExtCPD.model_validate({
            'id': pdu_interface.vld,
            'int-cpd': {'cpd': 'vdu_' + pdu_interface.vld, 'vdu-id': vdu_id}
        }))

        new_vdu_id = 'vdu_' + pdu_interface.vld
        if define_type:
            if pdu_interface.intf_type is None:
                pdu_interface.intf_type = 'VIRTIO'

            virtual_network_interface_requirement = [{
                'name': pdu_interface.name,
                'virtual-interface': {'type': pdu_interface.intf_type}
            }]
        else:
            virtual_network_interface_requirement = [{'name': pdu_interface.name}]

        res = IntCPD.model_validate({
            'id': new_vdu_id,
            'virtual-network-interface-requirement': virtual_network_interface_requirement
        })

        if pdu_interface.port_security_enabled:
            res.port_security_enabled = True

        return res

    def add_cloud_init(self, vnf_data: VirtualNetworkFunctionDescriptor, vdu: VDUSol006Descriptor) -> dict:
        content = "#cloud-config\n# vim:syntax=yaml\n"
        cloud_conf = {
            'debug': True,
            'ssh_pwauth': True,
            'password': vnf_data.password,
            'manage_etc_hosts': True,  # Add the instance hostname to the /etc/hosts file, this fixes 'sudo' slowness
            'disable_root': False,
            'chpasswd': {
                'list': [vnf_data.username + ":" + vnf_data.password],
                'expire': False
            },
            'runcmd': [
                "sed -i'.orig' -e's/PermitRootLogin .*/PermitRootLogin yes/' /etc/ssh/sshd_config",
                "sed -i'.orig' -e's/#PermitRootLogin .*/PermitRootLogin yes/' /etc/ssh/sshd_config",
                "service sshd restart"
            ]
        }

        filename = vdu.id + '_cloud_config.txt'
        vdu.cloud_init_file = filename

        return {'filename': filename, 'content': content + yaml.safe_dump(cloud_conf)}

    def add_charm(self, vnf_data: VirtualNetworkFunctionDescriptor) -> None:
        ex_environ = f'{HELM_FLEX_VNFM}_ee'
        primitive = CharmPrimitive.model_validate({
            'name': 'flexops',
            'execution-environment-ref': ex_environ,
            'parameter': [{'name': 'config-content', 'default-value': '', 'data-type': 'STRING'}],
        })

        initial_config = CharmPrimitive.model_validate({
            'name': 'config',
            'execution-environment-ref': ex_environ,
            'parameter': [{'name': 'ssh-hostname', 'value': '<rw_mgmt_ip>'},
                          {'name': 'ssh-username', 'value': vnf_data.username},
                          {'name': 'ssh-password', 'value': vnf_data.password}],
            'seq': '1'
        })
        # HELM
        ex_environ = CharmExecEnviron.model_validate({
            'id': ex_environ,
            'helm-chart': HELM_FLEX_VNFM,
            'external-connection-point-ref': self.vnfd_model.mgmt_cp
        })

        day12_elem: CharmDay12 = CharmDay12.model_validate({
            'id': self.vnfd_model.id,
            'config-primitive': [primitive],
            'execution-environment-list': [ex_environ],
            'initial-config-primitive': [initial_config]
        })

        lcm = LCMOperationConfig.model_validate({'operate-vnf-op-config': {'day1-2': [day12_elem]}})

        # Taking the flavor called 'default-df'
        df: DF = next((item for item in self.vnfd_model.df if item.id == 'default-df'), None)
        if df is None:
            raise ValueError('default-df missing in the vnfd')
        df.lcm_operations_configuration = lcm

    def create_package(self, vnf_data: VirtualNetworkFunctionDescriptor):
        """
        Create the VNFD package in the tmp folder. Then uploads the package into OSM such that can be used to deploy
        network services. The package build is based on self.vnfd_model!!!

        Args:
            vnf_data: data used to

        Returns:

        """
        base_path = VNF_BASE_PATH_PACKAGE.format(self.vnfd_model.id)
        # Checking the folder tree e clean the vnf folder if it already exists
        if not os.path.exists(VNF_BASE_PATH):
            os.makedirs(VNF_BASE_PATH)

        # If the path already exist then we remove it! (Remove /tmp/vnf_packages/{...}) folder
        if os.path.exists(base_path):
            shutil.rmtree(base_path, ignore_errors=True)

        # We create the base path
        os.makedirs(base_path)

        if self.cloud_init:
            # If cloud init then create the folder in the base path (/tmp/vnf_packages/{...}/cloud_init)
            os.makedirs(base_path + '/cloud_init')

            # For each VDU we create a cloud init file to enable ssh login with root and ssd
            for vdu in self.vnfd_model.vdu:
                cloudi = self.add_cloud_init(vnf_data, vdu)
                # We write the file # TODO use util to write file closing the file
                with open(base_path + "/cloud_init/" + cloudi['filename'], 'w') as stream_:
                    print("{}".format(cloudi['content']), file=stream_)

        # HELM based VNF-Manager
        # Create helm-chart folder
        os.makedirs(base_path + '/helm-charts')
        os.makedirs(base_path + '/helm-charts/' + HELM_FLEX_VNFM)
        # Copy the folder in the NFVCL code ./vnf_managers/helmflexvnfm inside /tmp/vnf_packages/{...}/helm-charts
        copytree('vnf_managers/' + HELM_FLEX_VNFM, base_path + '/helm-charts/' + HELM_FLEX_VNFM)

        # Writing the VNFD into the correspondent folder and file
        # /tmp/vnf_packages/{...}/helm-charts/self.vnfd_model.id + '_vnfd.yaml # TODO use utils and previous todo
        with open(base_path + "/" + self.vnfd_model.id + '_vnfd.yaml', 'w') as stream_:
            # Excluding none fields from output
            yaml.safe_dump({'vnfd': self.vnfd_model.model_dump(by_alias=True, exclude_none=True)}, stream_,
                           default_flow_style=False)

        # Build tar.gz package of folder /tmp/vnf_packages/{...}.tar.gz
        with tarfile.open(base_path + '.tar.gz', "w:gz") as tar:
            tar.add(base_path, arcname=os.path.basename(base_path))

        # Uploading the VNFD on OSM
        logger.info("onboarding vnfd " + self.vnfd_model.id)
        res = osm_nbi_util.vnfd_onboard(self.vnfd_model.id + '_vnfd')
        logger.debug(res)

    def add_vdu_df_model(self, deployment_flavor_name: str, insta_level: str, vdu_id: str, count: int = 1,
                         min_count: int = 1) -> None:
        # From the deployment flavor of the model, it takes the one corresponding to deployment_flavor_name
        df = next((item for item in self.vnfd_model.df if item.id == deployment_flavor_name), None)

        insta_level: InstantiationLevel
        insta_level = next((instant_level for instant_level in df.instantiation_level
                            if (instant_level.id == insta_level)), None)

        insta_level.vdu_level.append(VDULevel.model_validate({'vdu-id': vdu_id, 'number-of-instances': count}))
        df.vdu_profile.append(VDUProfile.model_validate({'id': vdu_id, 'min-number-of-instances': min_count}))

    def manage_pdu_model(self, pdu_du: PDUDeploymentUnit) -> PduModel:
        topo = Topology.from_db(db=db, nbiutil=osm_nbi_util, lock=RLock())
        candidate_pdu = topo.get_pdu(pdu_du.id)

        if not candidate_pdu:
            raise ValueError('pdu not present in the persistency layer')
        # check the pdu on osm
        pnf_manager = PNFmanager()
        osm_pdu = pnf_manager.get(pdu_du.id)
        # check if the pdu is already used
        logger.debug(osm_pdu)
        if osm_pdu is not None:
            logger.debug('PDU already onboarded on osm')

            # check if busy
            logger.debug(osm_pdu)
            if osm_pdu['_admin']['usageState'] == 'IN_USE':
                raise ValueError('pdu ' + osm_pdu['name'] + ' already in use. Aborting!')
            # delete and recreate
            res = pnf_manager.delete(pdu_du.id)
            logger.debug('deleting pdu: ' + str(res))
        obj = {
            'type': candidate_pdu['type'],
            'name': pdu_du.id,
            'shared': True,
        }
        vim_accounts = []
        # add all vim accounts
        for v in osm_nbi_util.get_vims():
            vim_accounts.append(v['_id'])
        obj['vim_accounts'] = vim_accounts

        interface = []
        for i in candidate_pdu['interface']:
            interface.append(
                {
                    # 'vld': i['vld'],
                    'name': i['name'],
                    'ip-address': str(i['ip_address']),
                    'vim-network-name': i['network_name'],
                    'mgmt': i['mgt']
                }
            )
        obj['interfaces'] = interface

        # onboard the pdu on osm
        pnf_manager.create(obj)
        return candidate_pdu
