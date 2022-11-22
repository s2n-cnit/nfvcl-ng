import os
import shutil
import tarfile
import typing
import yaml

import utils.persistency
from . import NbiUtil, PNFmanager
from utils.persistency import DB
from utils import create_logger


logger = create_logger('vnfd_manager')


def copytree(src, dst, symlinks=False, ignore=None):
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            shutil.copytree(s, d, symlinks, ignore)
        else:
            shutil.copy2(s, d)


class sol006_VNFbuilder:
    def __init__(self,
                 nbi_util: NbiUtil,
                 db: utils.persistency.DB,
                 vnf_data: dict,
                 charm_name: typing.Optional[str] = None,
                 cloud_init: bool = False,
                 adapt_interfaces=False) -> None:
        self.nbi_util = nbi_util
        self.db = db
        self.vnfd = {}
        if 'vdu' in vnf_data:
            vnf_data['mgmt-interface'] = {
                'cp': next(item for item in vnf_data['vdu'][0]['interface'] if item['mgt'])['vld']}
        elif 'kdu' in vnf_data:
            vnf_data['mgmt-interface'] = {
                'cp': next(item for item in vnf_data['kdu'][0]['interface'] if item['mgt'])['vld']}
        elif 'pdu' in vnf_data:
            vnf_data['mgmt-interface'] = {
                'cp': next(item for item in vnf_data['pdu'][0]['interface'] if item['mgt'])['vld']}
        else:
            raise ValueError('cannot find nor vdus or kdus in vnf_data!!')
        self.cloud_init = cloud_init
        self.charm_name = charm_name
        self.adapt_interfaces = adapt_interfaces
        self.topology_lock = None

        self.create_sol006_descriptor(vnf_data)
        if charm_name:
            self.add_charm(vnf_data)
        self.create_package(nbi_util, vnf_data)

    def get_id(self) -> str:
        return self.vnfd['id']

    def set_topology_lock(self, topo_lock) -> None:
        self.topology_lock = topo_lock

    def create_sol006_descriptor(self, vnf: dict) -> None:
        self.vnfd.update({
            'id': vnf['id'],
            'product-name': vnf['name'],
            'version': 2.0,
            'description': 'VNFd automatically generated by the NFVCL',
            'provider': 'CNIT S2N Lab',
            'mgmt-cp': vnf['mgmt-interface']['cp'],
            'vdu': [],
            'df': [{
                'id': 'default-df',
                'instantiation-level': [{
                    'id': 'default-instantiation-level',
                    'vdu-level': []
                }],
                'vdu-profile': []
            }],
            'ext-cpd': []
        })

        if 'vdu' in vnf:
            self.vnfd.update({'sw-image-desc': [], 'virtual-compute-desc': [], 'virtual-storage-desc': []})
            self.type = 'vnfd'

            for u in vnf['vdu']:
                vdu_obj = {
                    'id': u['id'],
                    'name': u['id'],
                    'int-cpd': [self.add_vdu_cp(i, u['id']) for i in u['interface']],
                    'sw-image-desc': u['image'],
                    'virtual-compute-desc': u['id'] + '_compute_desc',
                    'virtual-storage-desc': [u['id'] + '_storage_desc']
                }
                if 'vim-monitoring' in u:
                    vdu_obj['monitoring-parameter'] = self.add_vim_monitoring()

                # adding sw-image-desc, if not existing
                image_ref = next((item for item in self.vnfd['sw-image-desc'] if (item['name'] == u['name'])), None)
                if image_ref is None:
                    self.vnfd['sw-image-desc'].append({'id': u['image'], 'image': u['image'], 'name': u['image']})
                self.vnfd['virtual-compute-desc'].append({
                    'id': u['id'] + '_compute_desc',
                    'virtual-cpu': {'num-virtual-cpu': u['vm-flavor']['vcpu-count']},
                    'virtual-memory': {'size': str(int(u['vm-flavor']['memory-mb']) / 1024)}
                })
                # adding storage desc
                self.vnfd['virtual-storage-desc'].append(
                    {'id': u['id'] + '_storage_desc', 'size-of-storage': u['vm-flavor']['storage-gb']})
                self.vnfd['vdu'].append(vdu_obj)
                # adding deployment flavor
                self.add_vdu_df('default-df', 'default-instantiation-level', u['id'])

        if 'pdu' in vnf:
            self.type = 'pnfd'
            for u in vnf['pdu']:
                pdu = self.manage_pdu(self.nbi_util, self.db, u)
                # update the username and password
                vnf.update({'username': pdu['user'], 'password': pdu['passwd']})
                # now prepare the descriptor
                vdu_obj = {
                    'id': u['id'],
                    'name': u['id'],
                    'int-cpd': [self.add_vdu_cp(i, u['id'], define_type=False) for i in pdu['interface']],
                    'pdu-type': pdu['type']
                }
                self.vnfd['vdu'].append(vdu_obj)
                # adding deployment flavor
                self.add_vdu_df('default-df', 'default-instantiation-level', u['id'])

        if 'kdu' in vnf:
            logger.debug(vnf['kdu'])
            self.type = 'knfd'
            self.vnfd['kdu'] = []
            self.vnfd['k8s-cluster'] = {'nets': []}
            self.vnfd['ext-cpd'] = []
            for u in vnf['kdu']:
                self.vnfd['kdu'].append({'name': u['name'], 'helm-chart': u['helm-chart']})
                for n in u['interface']:
                    self.vnfd['k8s-cluster']['nets'].append({'id': n['k8s-cluster-net']})
                    self.vnfd['ext-cpd'].append({'id': n['vld'], 'k8s-cluster-net': n['k8s-cluster-net']})
                    if 'mgt' in n:
                        if n['mgt'] is True:
                            self.vnfd['mgmt-cp'] = n['vld']

    def add_vim_monitoring(self) -> list:
        # vdu_obj['monitoring-parameter'] = [
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

    def add_vdu_cp(self, intf: dict, vdu_id: str, define_type: bool = True) -> dict:
        # intf_type should not be set for pdu
        if define_type and 'intf_type' not in intf:
            intf['intf_type'] = 'VIRTIO'
        # mapping ex-cp to int-cp
        self.vnfd['ext-cpd'].append({
            'id': intf['vld'],
            'int-cpd': {'cpd': 'vdu_' + intf['vld'], 'vdu-id': vdu_id}
        })
        if define_type:
            res = {
                'id': 'vdu_' + intf['vld'],
                'virtual-network-interface-requirement': [{
                    'name': intf['name'],
                    'virtual-interface': {'type': intf['intf_type']}
                }]
            }
        else:
            res = {
                'id': 'vdu_' + intf['vld'],
                'virtual-network-interface-requirement': [{'name': intf['name']}]
            }
        if 'port-security-enabled' in intf:
            res['port-security-enabled'] = intf['port-security-enabled']
            # res['port-security-disable-strategy'] = 'full'
        return res

    def add_cloud_init(self, vnf_data: dict, vdu: dict) -> dict:
        content = "#cloud-config\n# vim:syntax=yaml\n"
        cloud_conf = {
            'debug': True,
            'ssh_pwauth': True,
            'password': vnf_data['password'],
            'disable_root': False,
            'chpasswd': {
                'list': [vnf_data['username'] + ":" + vnf_data['password']],
                'expire': False
            },
            'runcmd': [
                "sed -i'.orig' -e's/PermitRootLogin .*/PermitRootLogin yes/' /etc/ssh/sshd_config",
                "sed -i'.orig' -e's/#PermitRootLogin .*/PermitRootLogin yes/' /etc/ssh/sshd_config",
                "service sshd restart"
            ]
        }

        filename = vdu['id'] + '_cloud_config.txt'
        vdu['cloud-init-file'] = filename

        return {'filename': filename, 'content': content + yaml.safe_dump(cloud_conf)}

    def add_charm(self, vnf_data: dict) -> None:
        if self.charm_name not in ['flexcharm', 'flexcharm2', 'flexcharmvyos', 'helmflexvnfm']:
            raise ValueError('charm type not supported')
        primitive = {
            'name': 'flexops',
            'execution-environment-ref': self.charm_name + '_ee',
            'parameter': [{'name': 'config-content', 'default-value': '', 'data-type': 'STRING'}]
        }
        initial_config = {
            'name': 'config',
            'execution-environment-ref': self.charm_name + '_ee',
            'parameter': [{'name': 'ssh-hostname', 'value': '<rw_mgmt_ip>'},
                          {'name': 'ssh-username', 'value': vnf_data['username']},
                          {'name': 'ssh-password', 'value': vnf_data['password']}],
            'seq': '1'
        }
        if self.charm_name in ['flexcharm', 'flexcharm2', 'flexcharmvyos']:
            ex_environ = {'id': self.charm_name + '_ee', 'juju': {'charm': self.charm_name}}  # , 'cloud': 'k8scloud'}
        else:
            ex_environ = {
                'id': self.charm_name + '_ee',
                'helm-chart': self.charm_name,
                'external-connection-point-ref': self.vnfd['mgmt-cp']
            }

        day12_elem = {
            'id': self.vnfd['id'],
            # 'config-access': {'ssh-access': {'default-user': vnf_data['username'], 'required': True}},
            'config-primitive': [primitive],
            'execution-environment-list': [ex_environ],
            'initial-config-primitive': [initial_config]
        }
        lcm = {'operate-vnf-op-config': {'day1-2': [day12_elem]}}
        df = next((item for item in self.vnfd['df'] if item['id'] == 'default-df'), None)
        if df is None:
            raise ValueError('default-df missing in the vnfd')
        df['lcm-operations-configuration'] = lcm

    def create_package(self, nbi_util: NbiUtil, vnf_data: dict):
        self.base_path = '/tmp/vnf_packages/{}_vnfd'.format(self.vnfd['id'])
        # checking the folder tree e clean the vnf folder if it already exists
        if not os.path.exists('/tmp/vnf_packages'):
            os.makedirs('/tmp/vnf_packages')

        if os.path.exists(self.base_path):
            shutil.rmtree(self.base_path, ignore_errors=True)
        os.makedirs(self.base_path)

        if self.cloud_init:
            os.makedirs(self.base_path + '/cloud_init')

            for vdu in self.vnfd['vdu']:
                cloudi = self.add_cloud_init(vnf_data, vdu)
                with open(self.base_path + "/cloud_init/" + cloudi['filename'], 'w') as stream_:
                    print("{}".format(cloudi['content']), file=stream_)

        # juju-based VNF-Manager
        if self.charm_name and self.charm_name in ['flexcharm', 'flexcharm2', 'flexcharmvyos']:
            os.makedirs(self.base_path + '/charms')
            os.makedirs(self.base_path + '/charms/' + self.charm_name)
            # copytree('vnfd_templates/charms_v2/' + self.charm_name , self.base_path + '/charms/' + self.charm_name)
            copytree('vnf_charms/' + self.charm_name, self.base_path + '/charms/' + self.charm_name)

        if self.charm_name and self.charm_name in ['helmflexvnfm']:
            os.makedirs(self.base_path + '/helm-charts')
            os.makedirs(self.base_path + '/helm-charts/' + self.charm_name)
            # copytree('vnfd_templates/charms_v2/' + self.charm_name , self.base_path + '/charms/' + self.charm_name)
            copytree('vnf_managers/' + self.charm_name, self.base_path + '/helm-charts/' + self.charm_name)

        # dumping the descriptor
        with open(self.base_path + "/" + self.vnfd['id'] + '_vnfd.yaml', 'w') as stream_:
            yaml.safe_dump({'vnfd': self.vnfd}, stream_, default_flow_style=False)

        # build tar.gz package
        with tarfile.open(self.base_path + '.tar.gz', "w:gz") as tar:
            tar.add(self.base_path, arcname=os.path.basename(self.base_path))

        logger.info("onboarding vnfd " + self.vnfd['id'])
        res = nbi_util.vnfd_onboard(self.vnfd['id'] + '_vnfd')
        logger.debug(res)

    def add_vdu_df(self, deployment_flavor_name: str, insta_level: str, vdu_id: str, count: int = 1,
                   min_count: int = 1) -> None:
        df = next((item for item in self.vnfd['df'] if item['id'] == deployment_flavor_name), None)
        instalevel = next((item for item in df['instantiation-level'] if (item['id'] == insta_level)), None)
        instalevel['vdu-level'].append({'vdu-id': vdu_id, 'number-of-instances': count})
        df['vdu-profile'].append({'id': vdu_id, 'min-number-of-instances': min_count})

    def manage_pdu(self, nbi_util: NbiUtil, db: DB, u: dict) -> dict:
        topology = Topology.from_db(self.db, self.nbi_util, self.topology_lock)
        db_item = topology.get_pdu(u['id'])
        logger.debug(db_item)
        if db_item is None:
            raise ValueError('pdu not present in the persistency layer')
        # check the pdu on osm
        pnf_manager = PNFmanager()
        osm_pdu = pnf_manager.get(u['id'])
        # check if the pdu is already used
        logger.debug(osm_pdu)
        if osm_pdu is not None:
            logger.debug('PDU already onboarded on osm')

            # check if busy
            logger.debug(osm_pdu)
            if osm_pdu['_admin']['usageState'] == 'IN_USE':
                raise ValueError('pdu ' + osm_pdu['name'] + ' already in use. Aborting!')
            # delete and recreate
            res = pnf_manager.delete(u['id'])
            logger.debug('deleting pdu: ' + str(res))
        obj = {
            'type': db_item['type'],
            'name': u['id'],
            'shared': True,
        }
        vim_accounts = []
        # add all vim accounts
        for v in nbi_util.get_vims():
            vim_accounts.append(v['_id'])
        obj['vim_accounts'] = vim_accounts

        interface = []
        for i in db_item['interface']:
            interface.append(
                {
                    # 'vld': i['vld'],
                    'name': i['name'],
                    'ip-address': str(i['ip-address']),
                    'vim-network-name': i['vim-network-name'],
                    'mgmt': i['mgt']
                }
            )
        obj['interfaces'] = interface

        # onboard the pdu on osm
        pnf_manager.create(obj)
        return db_item
