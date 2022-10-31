from blueprints.blueprint import BlueprintBase
from blueprints.blueprint_utils import parse_ansible_output
from configurators.k8s_configurator import ConfiguratorK8s
from nfvo.vnf_manager import sol006_VNFbuilder
from nfvo.nsd_manager import sol006_NSD_builder, get_ns_vld_ip
from typing import Union, List, Dict, Optional
import traceback

from main import *

db = persistency.db()
logger = create_logger('K8sBlue')
nbiUtil = NbiUtil(username=osm_user, password=osm_passwd, project=osm_proj, osm_ip=osm_ip, osm_port=osm_port)


class K8s(BlueprintBase):
    def __init__(self, conf: dict, id_: str, data: Union[Dict, None] = None):
        BlueprintBase.__init__(self, conf, id_, data=data, nbiutil=nbiUtil, db=db)
        logger.info("Creating K8S Blueprint")
        self.supported_operations = {
            'init': [{
                'day0': [{'method': 'bootstrap_day0'}],
                'day2': [{'method': 'init_controller_day2_conf', 'callback': 'get_master_key'},
                         {'method': 'add_worker_day2'},
                         {'method': 'add_worker_area_label'}],
                'dayN': []
            }],
            'scale': [{
                'day0': [{'method': 'add_worker'}],
                'day2': [{'method': 'add_worker_day2'},
                         {'method': 'add_worker_area_label'}],
                'dayN': [{'method': 'del_worker'}]
            }],
            'nfvo_k8s_onboard': [{
                'day0': [],
                'day2': [{'method': 'onboard_k8s_cluster'}],
                'dayN': []
            }],
            'monitor': [{
                'day0': [],
                'day2': [{'method': 'enable_prometheus'}],
                'dayN': []
            }],
            'log': [{
                'day0': [],
                'day2': [{'method': 'enable_elk'}],
                'dayN': []
            }],
        }
        self.conf['config']['nfvo_onboarded'] = False
        self.primitives = []
        self.vnfd = {'core': [], 'area': []}
        core_area = next((item for item in self.conf['areas'] if item['core']), None)
        if core_area:
            self.conf['config']['core_area'] = core_area
        else:
            raise ValueError('Vim CORE not found in the input')

    def bootstrap_day0(self, msg: dict) -> list:
        self.topology_terraform(msg)
        return self.nsd()

    def topology_terraform(self, msg: dict) -> None:
        try:
            logger.debug("Blue {} - terraforming".format(self.get_id()))
            pool_list = []
            for _p in msg['config']['network_endpoints']['data_nets']:
                lb_pool = _p.copy()
                logger.debug("Blue {} - checking pool {}".format(self.get_id(), _p['net_name']))
                for area in msg['areas']:
                    logger.debug("Blue {} - checking area {}".format(self.get_id(), area['id']))
                    # check if the vim exists
                    vim = self.topology_get_vim_by_area(area['id'])
                    if not vim:
                        raise ValueError('Blue {} - no VIMs at area {}'.format(self.get_id(), area['id']))
                    # check if the load-balancing network exists at the VIM
                    if lb_pool['net_name'] not in vim['networks']:
                        raise ValueError('Blue {} - network {} not available at VIM {}'
                                         .format(self.get_id(), vim['name'], area['id']))

                net = self.topology_get_network(lb_pool['net_name'])

                lb_pool['cidr'] = net['cidr']

                if 'ip_start' not in lb_pool:
                    logger.debug("{} retrieving lb IP range".format(self.get_id()))
                    range_length = lb_pool['range_length'] if 'range_length' in lb_pool else 20

                    llb_range = self.topology_reserve_ip_range(lb_pool['net_name'], range_length)
                    logger.info("Blue {} taking range {}-{} on network {} for lb"
                                .format(self.get_id(), llb_range['start'], llb_range['end'], lb_pool['net_name']))
                    lb_pool['ip_start'] = llb_range['start']
                    lb_pool['ip_end'] = llb_range['end']
                pool_list.append(lb_pool)

            self.conf['config']['network_endpoints']['data_nets'] = pool_list

        except Exception:
            logger.error(traceback.format_exc())
            raise ValueError("Terraforming Error")

    def setVnfd(self, area: str, area_id: Optional[int] = None, vld: Optional[list] = None,
                vm_flavor_request: Optional[dict] = None) -> None:
        logger.debug("setting VNFd for " + area)

        vm_flavor = {'memory-mb': '4096', 'storage-gb': '8', 'vcpu-count': '2'}
        if vm_flavor_request is not None:
            vm_flavor.update(vm_flavor_request)

        if area == "core":
            interfaces = [{'vld': 'mgt', 'name': 'ens3', "mgt": True}]
            vnfd = sol006_VNFbuilder({
                'username': 'root',
                'password': 'root',
                'id': self.get_id() + '_k8s_master',
                'name': self.get_id() + '_k8s_master_vnf',
                'vdu': [{
                    'count': 1,
                    'id': 'VM',
                    'image': 'ubuntu1804',
                    'vm-flavor': vm_flavor,
                    'interface': interfaces,
                    'vim-monitoring': True
                }]}, charm_name='helmflexvnfm', cloud_init=True)
            self.vnfd['core'].append({'id': 'vnfd', 'name': vnfd.get_id(), 'vl': interfaces})

        if area == 'area':
            if area_id is None:
                raise ValueError("area is None in set Vnfd")
            if vld is None:
                raise ValueError("vlds for worker vnf are None in set Vnfd")

            interfaces = []
            intf_index = 3  # starting from ens3
            for l_ in vld:
                interfaces.append(
                    {
                        "vld": l_["vld"],
                        "name": "ens{}".format(intf_index),
                        "mgt": l_["mgt"],
                        "port-security-enabled": False
                    }
                )
                intf_index += 1

            vnfd = sol006_VNFbuilder({
                'username': 'root',
                'password': 'root',
                'id': '{}_k8s_worker_area_{}'.format(self.get_id(), area_id),
                'name': '{}_k8s_worker_area_{}'.format(self.get_id(), area_id),
                'vdu': [{
                    'count': 1,
                    'id': 'VM',
                    'image': 'ubuntu1804',
                    'vm-flavor': vm_flavor,
                    'interface': interfaces,
                    'vim-monitoring': True
                }]}, charm_name='helmflexvnfm', cloud_init=True)
            self.vnfd['area'].append(
                {'area_id': area_id, 'vnfd': [{'id': 'vnfd', 'name': vnfd.get_id(), 'vl': interfaces}]})

    def getVnfd(self, area: str, area_id: Optional[int] = None) -> list:
        if area == "core":
            logger.debug(self.vnfd['core'])
            return self.vnfd['core']

        if area == "area":
            if area_id is None:
                raise ValueError("area is None in getVnfd")
            area_obj = next((item for item in self.vnfd['area'] if item['area_id'] == area_id), None)
            if area_obj is None:
                raise ValueError("area not found in getting Vnfd")
            return area_obj['vnfd']

    def controller_nsd(self) -> str:
        logger.info("building controller NSD")
        self.setVnfd('core')
        # template = {'category': 'service', 'type': '1nic', 'flavors': {'include': ['1nic'], 'exclude': []}}
        param = {
            'name': '{}_k8s_controller'.format(self.get_id()),
            'id': '{}_k8s_controller'.format(self.get_id()),
            'type': 'master'
        }
        vim_net_mapping = [
            {'vld': 'mgt', 'vim_net': self.conf['config']['network_endpoints']['mgt'], "mgt": True}
        ]
        n_obj = sol006_NSD_builder(
            self.getVnfd('core'), self.get_vim_name(self.conf['config']['core_area']), param, vim_net_mapping)

        self.nsd_.append(n_obj.get_nsd())
        return param['name']

    def worker_nsd(self, area: dict, replica_id: int) -> str:
        logger.info("Blue {} - building worker NSD for replica {} at area {}"
                    .format(self.get_id(), replica_id, area['id']))
        vim_net_mapping = [
            {'vld': 'mgt', 'vim_net': self.conf['config']['network_endpoints']['mgt'], "mgt": True}
        ]
        for pool in self.conf['config']['network_endpoints']['data_nets']:
            if pool['net_name'] != vim_net_mapping[0]['vim_net']:
                vim_net_mapping.append(
                    {'vld': 'data_{}'.format(pool['net_name']), 'vim_net': pool['net_name'], "mgt": False}
                )

        vm_flavor = self.conf['config']['worker_flavors'].copy()
        if area['worker_flavor_override']:
            vm_flavor.update(area['worker_flavor_override'])

        # setting the vnf descriptor only for the first replica, the further ones will use the same descriptor
        if replica_id < 1:
            self.setVnfd('area', area['id'], vld=vim_net_mapping, vm_flavor_request=vm_flavor)

        param = {
            'name': '{}_k8s_worker_area_{}_replica_{}'.format(self.get_id(), area['id'], replica_id),
            'id': '{}_k8s_worker_area_{}_replica_{}'.format(self.get_id(), area['id'], replica_id),
            'type': 'worker'
        }

        n_obj = sol006_NSD_builder(
            self.getVnfd('area', area['id']), self.get_vim_name(area['id']), param, vim_net_mapping)

        n_ = n_obj.get_nsd()
        n_['area'] = area['id']
        n_['replica_id'] = replica_id
        self.nsd_.append(n_)
        return param['name']

    def nsd(self) -> List[str]:
        logger.info("Creating K8s Network Service Descriptors")
        nsd_names = [self.controller_nsd()]

        for b in self.conf['areas']:
            logger.info(
                "Blue {} - Creating K8s Worker Service Descriptors on area {}".format(self.get_id(), b['id']))
            for replica_id in range(b['workers_replica']):
                nsd_names.append(self.worker_nsd(b, replica_id))

        logger.info("NSDs created")
        return nsd_names

    def init_controller_day2_conf(self, msg):
        logger.debug("Triggering Day2 Config for K8S blueprint " + str(self.get_id()))
        res = []
        master_nsd = next(item for item in self.nsd_ if item['type'] == 'master')
        conf_ = ConfiguratorK8s(
                master_nsd['descr']['nsd']['nsd'][0]['id'], 1, self.get_id(), self.conf, role='master'
            ).dump()
        # saving the id of the action because we need to post process its output
        # self.action_to_check.append(conf_[0]['param_value']['action_id'])
        self.action_to_check.append(conf_[0]['primitive_data']['primitive_params']['config-content'])
        res += conf_
        logger.debug("K8s master configuration built")

        self.to_db()
        return res

    def add_worker_area_label(self, msg: dict):
        logger.debug("Blue {} - Triggering Day2 Add area label to workers ".format(self.get_id()))

        areas_to_label = [item['id'] for item in msg['areas']]
        workers_to_label = []
        for area_id in areas_to_label:
            conf_area = next((item for item in self.conf['areas'] if item['id'] == area_id), None)
            if not conf_area:
                raise ValueError('Blue {} - confifuration area {} not found'.format(self.get_id(), area_id))

            # looking for workers' vdu names (they are the names seen by the K8s master)
            vm_names = []
            for n in self.nsd_:
                if n['type'] == 'worker' and n['area'] == area_id:
                    vnfi = self.nbiutil.get_vnfi_list(n['nsi_id'])[0]
                    vm_names.append(vnfi['vdur'][0]['name'])
            workers_to_label.append({'area': area_id, 'vm_names': vm_names})

        configurator = ConfiguratorK8s(
            next(item['descr']['nsd']['nsd'][0]['id'] for item in self.nsd_ if item['type'] == 'master'),
            1,
            self.get_id(),
            self.conf,
            role='master'
        )
        configurator.add_worker_label(workers_to_label)
        return configurator.dump()

    def del_worker(self, msg: dict) -> List[str]:
        logger.info("Deleting worker from K8S blueprint " + str(self.get_id()))
        nsi_to_delete = []
        for area in msg['del_areas']:
            checked_area = next((item for item in self.conf['areas'] if item['id'] == area['id']), None)
            if not checked_area:
                raise ValueError("Blue {} - area {} not found".format(self.get_id(), area['id']))

            logger.debug("Blue {} - deleting K8s workers on area {}".format(self.get_id(), area['id']))
            # find nsi to be deleted
            for n in self.nsd_:
                if n['type'] == 'worker':
                    if n['area'] == area['id']:
                        logger.debug("Worker on area {} has nsi_id: {}".format(area['id'], n['nsi_id']))
                        nsi_to_delete.append(n['nsi_id'])
            # removing items from conf
            # Note: this should be probably done, after deletion confirmation from the nfvo
            self.conf['areas'] = [item for item in self.conf['areas'] if item['id'] != area['id']]

        for area in msg['modify_areas']:
            # check if area is already existing in self.conf, or it is a new area
            checked_area = next((item for item in self.conf['areas'] if item['id'] == area['id']), None)
            if checked_area:
                # area already existing, checking replicas
                if checked_area['workers_replica'] > area['workers_replica']:
                    nsi_ids = [item for item in self.nsd_ if item['area'] == area['id']]
                    logger.info("Blue {} - from area {} removing service instances: {}"
                                .format(self.get_id(), area['id'], nsi_ids))
                    nsi_to_delete.extend(nsi_ids[0:(checked_area['workers_replica'] - area['workers_replica'])])
                    checked_area['workers_replica'] = area['workers_replica']
                elif checked_area['workers_replica'] == area['workers_replica']:
                    logger.warn("Blue {} - no workers to be added on area {}".format(self.get_id(), area['id']))

        return nsi_to_delete

    def add_worker(self, msg: dict) -> List[str]:
        logger.info("Adding worker to K8S blueprint " + str(self.get_id()))
        nsd_names = []
        for area in msg['add_areas']:
            logger.info("Blue {} - activating new area {}".format(self.get_id(), area['id']))
            # check if area is already existing in self.conf, or it is a new area
            checked_area = next((item for item in self.conf['areas'] if item['id'] == area['id']), None)
            if checked_area:
                raise ValueError("Blue {} - area {} already exists!".format(self.get_id(), area['id']))
            for index in range(1, area['workers_replica']):
                logger.info("Blue {} - adding worker {} on area {}".format(self.get_id(), index, area['id']))
                nsd_names.append(self.worker_nsd(area, index))
            self.conf['areas'].append(area)

        for area in msg['modify_areas']:
            # check if area is already existing in self.conf, or it is a new area
            checked_area = next((item for item in self.conf['areas'] if item['id'] == area['id']), None)
            if checked_area:
                # area already existing, checking replicas
                if checked_area['workers_replica'] < area['workers_replica']:
                    for index in range(checked_area['workers_replica'] + 1, area['workers_replica']):
                        logger.info("Blue {} - adding worker {} on area {}".format(self.get_id(), index, area['id']))
                        nsd_names.append(self.worker_nsd(area, index))
                elif checked_area['workers_replica'] == area['workers_replica']:
                    logger.warn("Blue {} - no workers to be added on area {}".format(self.get_id(), area['id']))
                else:
                    logger.warn("Blue {} - workers to be deleted on area {}!!!".format(self.get_id(), area['id']))
                    # FIXME: how to deal with dayN?

        return nsd_names

    def add_worker_day2(self, msg: dict):  # FIXME!!!!!
        res = []

        for area in msg['areas']:
            # vdu_names = []
            for n in self.nsd_:
                if n['type'] == 'worker' and n['area'] == area['id']:
                    # vnfi = self.nbiutil.get_vnfi_list(n['nsi_id'])[0]
                    # vdu_names.append(vnfi['vdur'][0]['name'])
                    conf_ = ConfiguratorK8s(
                        n['descr']['nsd']['nsd'][0]['id'],
                        1,
                        self.get_id(),
                        self.conf,
                        role='worker',
                        master_key=self.conf['master_key_add_worker'],

                    ).dump()
            # saving the id of the action because we need to post process its output
            # self.action_to_check.append(conf_[0]['param_value']['action_id'])
            res += conf_
        logger.debug("K8s worker configuration built")
        self.to_db()
        return res

    def get_ip(self) -> None:
        logger.debug('getting IP addresses from vnf instances')

        for n in self.nsd_:
            if n['type'] == 'master':
                # logger.debug('analyzing epc vlds')
                vlds = get_ns_vld_ip(n['nsi_id'], ["mgt"])
                self.conf['config']['controller_ip'] = vlds["mgt"][0]['ip']
            if n['type'] == 'worker':
                area = next(item for item in self.conf['areas'] if item['id'] == n['area'])
                if 'worker_data_ip' not in area:
                    area['worker_data_ip'] = {}
                # links
                vld_names = ["mgt"]
                for pool in self.conf['config']['network_endpoints']['data_nets']:
                    if pool['net_name'] != self.conf['config']['network_endpoints']['mgt']:
                        vld_names.append('data_{}'.format(pool['net_name']))

                vlds = get_ns_vld_ip(n['nsi_id'], vld_names)
                # writing data under the conf tree

                # vlds with only one vnf:
                area['worker_mgt_ip'] = vlds["mgt"][0]['ip']  # FIXME multiple IPs for multiple replicas
                area['worker_data_ip'][n['replica_id']] = [{"net": item, "ip": vlds[item][0]['ip']} for item in vlds]
        self.to_db()

    def get_master_key(self, callback_msg):
        for primitive in callback_msg:
            if primitive['result']['charm_status'] != 'completed':
                raise ValueError('in k8s blue -> get_master_key callback charm_status is not completed')

            logger.warn(primitive['primitive'])
            playbook_name = \
                primitive['primitive']['primitive_data']['primitive_params']['config-content']['playbooks'][0]['name']
            # action_id = primitive['result']['details']['detailed-status']['output']
            action_id = primitive['primitive']['primitive_data']['primitive_params']['config-content']['action_id']

            action_output = db.findone_DB('action_output', {'action_id': action_id})
            logger.debug('**** retrieved action_output {}'.format(action_output['action_id']))

            # retrieve data from action output
            self.conf['master_key_add_worker'] = parse_ansible_output(action_output, playbook_name,
                                                                      'worker join key', 'msg')
            self.conf['config']['master_credentials'] = parse_ansible_output(action_output, playbook_name,
                                                                             'k8s credentials', 'msg')['stdout']
        self.to_db()
        if 'nfvo_onboard' in self.conf:
            if self.conf['nfvo_onboard']:
                self.onboard_k8s_cluster({})

    def onboard_k8s_cluster(self, msg: dict):
        core_vim = self.get_vim(self.conf['config']['core_area'])
        if core_vim is None:
            raise ValueError('onboard_k8s_cluster -> core vim is None')

        k8s_version = self.conf['config']['version']
        k8s_nets = {'data_net': self.conf['config']['network_endpoints']['data_nets'][0]['net_name']}  # FIXME: only 1?

        res = nbiUtil.add_k8s_cluster(
            self.get_id(),  # <- name
            yaml.safe_load(self.conf['config']['master_credentials']),
            k8s_version,
            nbiUtil.get_vim_by_tenant_and_name(core_vim['name'], core_vim['tenant'])['_id'],
            k8s_nets
        )
        logger.info(res)
        if res:
            self.conf['config']['nfvo_onboarded'] = True

        return []

    def _destroy(self):
        logger.info("Destroying")
        if self.conf['config']['nfvo_onboarded']:
            nbiUtil.delete_k8s_cluster(self.get_id())

        nbiUtil.delete_k8s_repo(self.get_id())

        # release the reserved IP addresses for the LB
        self.topology_release_ip_range()
