from utils.util import create_logger
from utils.ipam import *
from topology.vim_terraform import VimTerraformer
from topology.rest_topology_model import TopologyModel, PduModel
from utils.persistency import OSSdb
from nfvo.osm_nbi_util import NbiUtil
import typing
import json
import traceback
from multiprocessing import RLock, Queue
from utils.util import obj_multiprocess_lock, redis_host, redis_port
import redis

topology_msg_queue = Queue()
topology_lock = RLock()

logger = create_logger('Topology')
redis_cli = redis.Redis(host=redis_host, port=redis_port, decode_responses=True, encoding="utf-8")


class Topology:
    def __init__(self, topo: Union[dict, None], db: OSSdb, nbiutil: NbiUtil, lock: RLock):
        self.db = db
        self.nbiutil = nbiutil
        self.lock = lock
        self._os_terraformer = {}
        if topo:
            if isinstance(topo, TopologyModel):
                self._data = topo.dict()
            else:
                try:
                    self._data = TopologyModel.parse_obj(topo).dict()
                except Exception:
                    logger.error(traceback.format_exc())
                    raise ValueError("Topology cannot be initialized")

            # re-creating terraformer objs
            for vim in self._data['vims']:
                logger.debug('creating terraformer object for VIM {}'.format(vim['name']))
                self._os_terraformer[vim['name']] = VimTerraformer(vim)
        else:
            logger.warn("topology information are not existing")
            self._data = {'vims': [], 'networks': [], 'routers': [], 'kubernetes': [], 'pdus': []}

    @classmethod
    def from_db(cls, db: OSSdb, nbiutil: NbiUtil, lock: RLock):
        topo = db.findone_DB("topology", {})
        data = TopologyModel.parse_obj(topo).dict()
        return cls(data, db, nbiutil, lock)

    def save_topology(self) -> None:
        content = TopologyModel.parse_obj(self._data)
        plain_dict = json.loads(content.json())
        self.db.update_DB("topology", plain_dict, {'id': 'topology'})

    # **************************** Topology ***********************
    def get(self) -> dict:
        return self._data

    @obj_multiprocess_lock
    def create(self, topo: dict, terraform: bool = False) -> None:
        logger.debug("terraform: {}".format(terraform))
        if len(self._data['vims']) or len(self._data['networks']) or len(self._data['routers']):
            logger.error('not possible to allocate a new topology, since another one is already declared')
            raise ValueError('not possible to allocate a new topology, since another one is already declared')
        self._data = topo
        for vim in self._data['vims']:
            logger.info('starting terraforming VIM {}'.format(vim['name']))
            # self.os_terraformer[vim['name']] = VimTerraformer(vim)
            self.add_vim(vim, terraform=terraform)
        msg = {
            'operation': 'create',
            'data': topo
        }
        redis_cli.publish('topology', json.dumps(msg))

    @obj_multiprocess_lock
    def delete(self, terraform: bool = False) -> None:
        logger.debug("[delete] terraform: {}".format(terraform))
        if not self._data:
            logger.error('not possible to delete the topology. No topology is currently allocated')
            raise ValueError('not possible to delete the topology. No topology is currently allocated')

        if terraform:
            for vim in self._data['vims']:
                error: Exception
                try:
                    self.del_vim(vim)
                except Exception as error:
                    logger.error("{}".format(error))
                    raise error

        self._os_terraformer = {}
        self._data = {'vims': [], 'networks': [], 'routers': [], 'kubernetes': [], 'pdus': []}
        self.db.delete_DB('topology', {'id': 'topology'})
        msg = {
            'operation': 'delete',
            'data': {}
        }
        redis_cli.publish('topology', json.dumps(msg))

    # **************************** VIMs ****************************
    def get_vim(self, vim_name: str) -> Union[dict, None]:
        vim = next((item for item in self._data['vims'] if item['name'] == vim_name), None)
        if not vim:
            raise ValueError('vim {} not found in the topology'.format(vim_name))
        return vim

    @obj_multiprocess_lock
    def add_vim(self, vim, terraform: bool = False):
        # check if the vim already exists
        if vim['name'] in self._os_terraformer:
            raise ValueError('VIM already existing')
        else:
            self._os_terraformer[vim['name']] = VimTerraformer(vim)
        if terraform:
            for vim_net in vim['networks']:
                logger.debug('now analyzing network {}'.format(vim_net['name']))
                self.add_vim_net(vim_net, vim)

            for vim_router in vim['routers']:
                self.add_vim_router(vim_router, vim)

        self._data['vims'].append(vim)

        use_floating_ip = False
        for vim_net in vim['networks']:
            use_floating_ip = use_floating_ip or self.check_fip(vim_net)

        osm_vim = {}
        for key in ["schema_version", "name", "vim_type", "vim_tenant_name", "vim_user", "vim_password",
                    "config"]:
            if key in vim:
                osm_vim[key] = vim[key]
        osm_vim['config']['use_floating_ip'] = use_floating_ip
        osm_vim['vim_url'] = str(vim['vim_url'])

        data = self.nbiutil.add_vim(osm_vim)
        if not data:
            raise ValueError("failed to onboard VIM {} onto OSM".format(vim['name']))
        msg = {
            'operation': 'create_vim',
            'data': vim
        }
        redis_cli.publish('topology', json.dumps(msg))

    @obj_multiprocess_lock
    def del_vim(self, vim, terraform=False):
        # FixMe: if there are services on the VIM, OSM will not delete it
        try:
            osm_vim = self.nbiutil.get_vim_by_tenant_and_name(vim['name'], vim['vim_tenant_name'])
            logger.debug(osm_vim)
        except ValueError:
            logger.error('VIM {} not found at osm, skipping...'.format(vim['name']))
        else:
            logger.info('removing VIM {} from osm'.format(vim['name']))
            data = self.nbiutil.del_vim(osm_vim['_id'])
            logger.debug(data)

        if terraform:
            # remove all networks, ports and routers
            for router in self._data['routers']:
                if router['name'] in vim['routers']:
                    self._os_terraformer[vim['name']].delRouter(router['name'])
            for network in self._data['networks']:
                if network['name'] in [item['name'] for item in vim['networks']]:
                    self._os_terraformer[vim['name']].delNet(network['name'])

        self._data['vims'] = [item for item in self._data['vims'] if item['name'] != vim['name']]
        msg = {
            'operation': 'delete_vim',
            'data': vim
        }
        redis_cli.publish('topology', json.dumps(msg))

    @obj_multiprocess_lock
    def update_vim(self, update_msg: dict, terraform: bool = True):
        vim = next((item for item in self._data['vims'] if item['name'] == update_msg['name']), None)
        if not vim:
            raise ValueError('vim {} not found in the topology'.format(update_msg['name']))

        for vim_net in update_msg['networks_to_add']:
            logger.debug("adding net {} to vim {}".format(vim_net, vim['name']))
            if vim_net in vim['networks']:
                raise ValueError('network {} already in VIM {}'.format(vim_net, vim['name']))
            self.add_vim_net(vim_net, vim, terraform=terraform)
        for vim_net in update_msg['networks_to_del']:
            logger.debug("deleting net {} from vim {}".format(vim_net, vim['name']))
            if vim_net not in vim['networks']:
                raise ValueError('network {} not in VIM {}'.format(vim_net, vim['name']))
            self.del_vim_net(vim_net, vim, terraform=terraform)
        for vim_router in update_msg['routers_to_add']:
            logger.debug("adding router {} from vim {}".format(vim_router, vim['name']))
            self.add_vim_router(vim_router, vim, terraform=terraform)
        for vim_router in update_msg['routers_to_del']:
            logger.debug("deleting router {} from vim {}".format(vim_router, vim['name']))
            self.del_vim_router(vim_router, vim, terraform=terraform)
        for vim_area in update_msg['areas_to_add']:
            logger.debug("adding area {} to vim {}".format(vim_area, vim['name']))
            if vim_area in vim['areas']:
                raise ValueError('area {} already in VIM {}'.format(vim_area, vim['name']))
            vim['areas'].append(vim_area)
        for vim_area in update_msg['areas_to_del']:
            logger.debug("deleting area {} from vim {}".format(vim_area, vim['name']))
            if vim_area not in vim['areas']:
                raise ValueError('area {} not in VIM {}'.format(vim_area, vim['name']))
            vim['areas'].pop(vim_area)
        msg = {
            'operation': 'update_vim',
            'data': vim
        }
        redis_cli.publish('topology', json.dumps(msg))

    def get_vim_name_from_area_id(self, area: str) -> Union[str, None]:
        vim = next((item for item in self._data['vims'] if area in item['areas']), None)
        if vim:
            return vim['name']
        else:
            return None

    def get_vim_from_area_id(self, area: str) -> dict:
        return next((item for item in self._data['vims'] if area in item['areas']), None)

    # **************************** Networks *************************
    def get_network(self, net_name: str, vim_name: typing.Optional[str] = None) -> dict:
        net = next((item for item in self._data['networks'] if item['name'] == net_name), None)
        if not net:
            raise ValueError('network {} not found in the topology'.format(net_name))
        if vim_name:
            vim = self.get_vim(vim_name)
            vim_net = next((item for item in vim['networks'] if item['name'] == net_name), None)
            if not vim_net:
                raise ValueError('network {} not found in the topology vim {}'.format(net_name, vim_name))
            # merging info from topology and vim router descriptions
            res = net.copy()
            res.update(vim_net)
            return res
        else:
            return net

    @obj_multiprocess_lock
    def add_network(self, network: dict, vim_names_list: Union[list, None] = None, terraform: bool = False):
        # it adds a network to the topology
        self._data['networks'].append(network)

        if vim_names_list:
            for vim_name in vim_names_list:
                vim = next((item for item in self._data['vims'] if item['name'] == vim_name), None)
                if vim is None:
                    raise ValueError('VIM {} not found'.format(vim_name))
                # vim['networks'].append(network['name'])
                self.add_vim_net(network['name'], vim, terraform=terraform)
        msg = {
            'operation': 'create_network',
            'data': network
        }
        redis_cli.publish('topology', json.dumps(msg))

    @obj_multiprocess_lock
    def del_network(self, network: dict, vim_names_list: Union[list, None] = None, terraform: bool = False):
        if vim_names_list:
            for vim_name in vim_names_list:
                vim = next((item for item in self._data['vims'] if item['name'] == vim_name), None)
                if vim is None:
                    raise ValueError('VIM {} not found'.format(vim_name))

                if network['name'] not in vim['networks']:
                    logger.warn('Network {} not found in VIM {}'.format(network['name'], vim['name']))
                else:
                    self.del_vim_net(network['name'], vim, terraform=terraform)
        self._data['networks'] = [item for item in self._data['networks'] if item['name'] != network['name']]
        msg = {
            'operation': 'delete_network',
            'data': network
        }
        redis_cli.publish('topology', json.dumps(msg))

    # **************************** Routers **************************

    def get_router(self, router_name: str, vim_name: typing.Optional[str] = None):
        router = next((item for item in self._data['routers'] if item['name'] == router_name), None)
        if not router:
            raise ValueError('router {} not found in the topology'.format(router_name))
        if vim_name:
            vim = self.get_vim(vim_name)
            vim_router = next((item for item in vim['routers'] if item['name'] == router_name), None)
            # merging info from topology and vim router descriptions
            res = router.copy()
            res.update(vim_router)
            return res
        else:
            return router

    @obj_multiprocess_lock
    def add_router(self, router: dict):
        # check if a router with the same name exists
        router_check = next((item for item in self._data['routers'] if item['name'] == router['name']), None)
        if router_check:
            raise ValueError("router {} already existing in the topology". format(router['name']))
        self._data['routers'].append(router)
        msg = {
            'operation': 'create_router',
            'data': router
        }
        redis_cli.publish('topology', json.dumps(msg))

    @obj_multiprocess_lock
    def del_router(self, router: dict, vim_names_list: list = None):
        router_check = next((item for item in self._data['routers'] if item['name'] == router['name']), None)
        if not router_check:
            raise ValueError("router {} not existing in the topology".format(router['name']))

        if vim_names_list:
            for vim_name in vim_names_list:
                vim = next((item for item in self._data['vims'] if item['name'] == vim_name), None)
                if vim is None:
                    raise ValueError('VIM {} not found'.format(vim_name))

                if router['name'] not in [item['name'] for item in vim['routers']]:
                    logger.warn('Router {} not found in VIM {}'.format(router['name'], vim['name']))
                else:
                    self.del_vim_router(router['name'], vim)

        self._data['routers'] = [item for item in self._data['routers'] if item['name'] != router['name']]
        msg = {
            'operation': 'delete_router',
            'data': router
        }
        redis_cli.publish('topology', json.dumps(msg))

    # **************************** VIM updating **********************

    def add_vim_net(self, vim_net_name: str, vim: dict, terraform: bool = False):
        if not self.check_vim_resource(vim_net_name, vim, 'networks'):
            logger.error('network {} already associated to the VIM'.format(vim_net_name))
            raise ValueError('Topology terraforming failed')

        vim['networks'].append(vim_net_name)
        net = next(item for item in self._data['networks'] if item['name'] == vim_net_name)
        if terraform:
            logger.info('network {} will be terraformed to vim {}'.format(vim_net_name, vim['name']))
            # net_overridden = net.copy()
            # net_overridden.update(vim_net)
            ids = self._os_terraformer[vim['name']].createNet(net.copy())
            ids['vim'] = vim['name']

            if 'ids' not in net:
                net['ids'] = []
            net['ids'].append(ids)
            return ids
        else:
            return None

    def del_vim_net(self, vim_net_name: str, vim: dict, terraform: bool = False):
        if self.check_vim_resource(vim_net_name, vim, 'networks'):
            logger.error('network {} not associated to the VIM'.format(vim_net_name))
            raise ValueError('Topology terraforming failed')
        vim['networks'].remove(vim_net_name)
        if terraform:
            return self._os_terraformer[vim['name']].delNet(vim_net_name)
        else:
            return True

    def check_vim_resource(self, resource_name: str, vim: dict, resource_type: str) -> bool:
        res = next((item for item in self._data[resource_type] if item['name'] == resource_name), None)
        if res is None:
            logger.error('{}} {} not found in the topology'.format(resource_type, resource_name))
            raise ValueError('Topology terraforming failed')
        check_vim_resource = next((item for item in vim[resource_type] if item == resource_name), None)
        return check_vim_resource is None

    def del_vim_router(self, vim_router_name: str, vim: dict, terraform: bool = False):
        if self.check_vim_resource(vim_router_name, vim, 'routers'):
            logger.error('router {} not associated to the VIM'.format(vim_router_name))
            raise ValueError('Topology terraforming failed')
        # router = next((item for item in self._data['routers'] if item['name'] == vim_router_name), None)
        vim['routers'].remove(vim_router_name)
        if terraform:
            return self._os_terraformer[vim['name']].delRouter(vim_router_name)
        else:
            return True

    def add_vim_router(self, vim_router_name: str, vim: dict, terraform: bool = False):
        if not self.check_vim_resource(vim_router_name, vim, 'routers'):
            logger.error('router {} already associated to the VIM'.format(vim_router_name))
            raise ValueError('Topology terraforming failed')
        topology_router = next((item for item in self._data['routers'] if item['name'] == vim_router_name), None)

        # override topology level data with vim-specific data
        router = topology_router.copy()
        # router.update(vim_router)

        # check if the router is connected to an external network
        router['internal_net'] = []
        for port in router['ports']:
            ext_net = next((item for item in
                            self._data['networks'] if item['name'] == port['net'] and item['external']), None)
            if ext_net:
                # this is an external router
                ids = next((item for item in ext_net['ids'] if item['vim'] == vim['name']), None)

                router["external_gateway_info"] = {
                    "network_id": ids['l2net_id'],
                    "enable_snat": True,
                    "external_fixed_ips": [
                        {
                            "ip_address": port['ip_addr'] if 'ip_addr' in port else
                            ext_net['allocation_pool'][0]['start'],
                            "subnet_id": ids['l3net_id']
                        }
                    ]
                }
            else:
                router['internal_net'].append(port['net'])

        logger.debug('internal networks:')
        logger.debug(router['internal_net'])
        if terraform:
            ids = self._os_terraformer[vim['name']].createRouter(router)
        else:
            ids = []
        return ids

    def get_routers_in_net(self, net_name: str):
        res = []
        for router in self._data['routers']:
            # check if the net is connected to this router
            net_port = next((item for item in router['ports'] if item['net'] == net_name), None)
            if net_port is not None:
                res.append(router)
        return res

    # **************************** Other funcs **********************
    # endpoints are network where VM (and VNFs) can be attached
    def get_network_endpoints(self, os_name=None):
        if os_name:
            os_nets = next((item['networks'] for item in self._data['vims'] if os_name == item['name']), [])
            net_names = [item['name'] for item in os_nets]
            return [item for item in self._data['networks'] if not item['external'] and item['name'] in net_names]
        else:
            return [item['name'] for item in self._data['networks'] if not item['external']]

    def check_fip(self, net_name: str) -> bool:
        # network require a floating IP if at least one of the router attached is external
        net_routers = self.get_routers_in_net(net_name)
        for router in net_routers:
            # check if the net is connected to this router
            if "external_gateway_info" in router and "enable_snat" in router["external_gateway_info"] and \
                    router["external_gateway_info"]["enable_snat"] is True:
                return True
        return False

    @obj_multiprocess_lock
    def reserve_range(self, net_name: str, range_length: int, owner: str, vim_name: typing.Optional[str] = None) \
            -> dict:
        net = self.get_network(net_name, vim_name)
        reserved_ips = net['allocation_pool'] if 'reserved_ranges' not in net \
            else net['allocation_pool'] + net['reserved_ranges']
        ip_range = get_range_in_cidr(net['cidr'], reserved_ips, range_length)
        self.set_reserved_ip_range(ip_range, net_name, owner)

        self.save_topology()
        return ip_range

    def set_reserved_ip_range(self, ip_range: dict, net_name: str, owner: str) -> None:
        topology_net = next((n for n in self._data['networks'] if n['name'] == net_name), None)
        if not topology_net:
            raise ValueError('network {} not found in the topology'.format(net_name))
        if topology_net['external']:
            raise ValueError('network {} is external. Not possible to reserve any IP ranges.'.format(net_name))
        if 'reserved_ranges' not in topology_net:
            topology_net['reserved_ranges'] = []
        ip_range['owner'] = owner
        topology_net['reserved_ranges'].append(ip_range)

    @obj_multiprocess_lock
    def release_ranges(self, owner: str, ip_range: typing.Optional[dict] = None, net_name: typing.Optional[str] = None):
        if net_name is None:
            for n in self._data['networks']:
                if 'reserved_ranges' in n:
                    n['reserved_ranges'] = [p for p in n['reserved_ranges'] if p['owner'] != owner]
        else:
            n = next((n for n in self._data['networks'] if n['name'] == net_name), None)
            if n is None:
                logger.error('network not found in the topology. Aborting IP range release')
            else:
                if 'reserved_ranges' in n:
                    if ip_range is None:
                        n['reserved_ranges'] = [p for p in n['reserved_ranges'] if p['owner'] != owner]
                    else:
                        n['reserved_ranges'] = [p for p in n['reserved_ranges'] if p['owner'] != owner and
                                                p['start'] != ip_range['start']]
        self.save_topology()

    @obj_multiprocess_lock
    def add_pdu(self, pdu_input: Union[PduModel, dict]):
        status = "error"
        details = ""
        if type(pdu_input) is PduModel:
            pdu = pdu_input.dict()
        else:
            pdu = PduModel.parse_obj(pdu_input).dict(by_alias=True)
        try:
            # pdu_list = self.nbiutil.get_pdu_list()
            pdu_check = next((item for item in self._data['pdus'] if item['name'] == pdu['name']), None)
            if pdu_check:
                raise ValueError('PDU {} already existing'.format(pdu['name']))

            # status = "not onboarded"
            pdu.update({'nfvo-onboarded': False, "details": ""})
            self._data['pdus'].append(pdu)
            self.save_topology()
            msg = {
                'operation': 'create_pdu',
                'data': json.loads(PduModel.parse_obj(pdu).json())
            }
            redis_cli.publish('topology', json.dumps(msg))
            self.save_topology()

        except Exception:
            logger.error(traceback.format_exc())
            details = "{}".format(traceback.format_exc())
            pdu.update({'nfvo-onboarded': False, "details": details})
            pdu_candidate = next((item for item in self._data['pdus'] if item['name'] == pdu['name']), None)
            if not pdu_candidate:
                self._data['pdus'].append(pdu)
            self.save_topology()

    @obj_multiprocess_lock
    def del_pdu(self, pdu_name: str):
        try:
            pdu = next(item for item in self._data['pdus'] if item['name'] == pdu_name)
            res = False
            if pdu['nfvo-onboarded']:
                res = self.nbiutil.delete_pdu(pdu_name)
                logger.info("Deleting pdu from OSM, result: {}".format(res))
            if res:
                self._data['pdus'] = [item for item in self._data['pdus'] if item['name'] != pdu_name]
            msg = {
                'operation': 'delete_pdu',
                'data': pdu
            }
            redis_cli.publish('topology', json.dumps(msg))
            self.save_topology()

        except ValueError as err:
            logger.error(err)
            raise ValueError('error in creating PDU')
        except Exception:
            logger.error(traceback.format_exc())

    def get_pdu(self, pdu_name: str):
        return next((item for item in self._data['pdus'] if item['name'] == pdu_name), None)

    def get_pdus(self):
        return self._data['pdus']

    def get_k8scluster(self):
        return self._data['kubernetes']

    @obj_multiprocess_lock
    def add_k8scluster(self, data: dict):
        # check if clusters with the same name exists

        k8s_cluster = next((item for item in self._data['kubernetes'] if item['name'] == data['name']), None)
        if k8s_cluster:
            raise ValueError('Kubernetes cluster with name {} already exists in the topology'.format(data['name']))

        self._data['kubernetes'].append(data)
        if 'nfvo_onboard' in data and data['nfvo_onboard']:
            self._data['kubernetes'][-1]['nfvo_status'] = 'onboarding'
            # Fixme use pydantic model?
            vims = self.nbiutil.get_vims()
            # retrieve vim_id using vim_name
            vim_id = next((item['_id'] for item in vims if item['name'] == data['vim_name'] and '_id' in item), None)
            if vim_id is None:
                raise ValueError('VIM (name={}) has not a vim_id'.format(data['vim_name']))
            if self.nbiutil.add_k8s_cluster(
                    data['name'],
                    data['credentials'],
                    data['k8s_version'],
                    vim_id,
                    data['networks']
            ):
                self._data['kubernetes'][-1]['nfvo_status'] = 'onboarded'
            else:
                self._data['kubernetes'][-1]['nfvo_status'] = 'error'
        redis_cli.publish('topology', json.dumps(data))
        self.save_topology()

    @obj_multiprocess_lock
    def del_k8scluster(self, name: str):
        # check if it exists
        k8s_cluster = next(item for item in self._data['kubernetes'] if item['name'] != name)

        if k8s_cluster['nfvo_status'] == 'onboarded':
            if not self.nbiutil.delete_k8s_cluster(name):
                raise ValueError('Kubernetes {} cannot be de-onboarded... still in use? Aborting...'.format(name))

        self._data['kubernetes'] = [item for item in self._data['kubernetes'] if item['name'] != name]

        redis_cli.publish('topology', json.dumps(k8s_cluster))
        self.save_topology()

    @obj_multiprocess_lock
    def update_k8scluster(self, name: str, data: dict):
        cluster = next(item for item in self._data['kubernetes'] if item['name'] == name)
        if cluster['nfvo_status'] != 'onboarded' and 'nfvo_onboard' in data and data['nfvo_onboard']:
            cluster.update(data)
            cluster['nfvo_status'] = 'onboarding'
            # Fixme use pydantic model?
            if self.nbiutil.add_k8s_cluster(
                    cluster['name'],
                    cluster['credentials'],
                    cluster['k8s_version'],
                    cluster['vim_name'],
                    cluster['networks']
            ):
                cluster['nfvo_status'] = 'onboarded'
            else:
                cluster['nfvo_status'] = 'error'
        redis_cli.publish('topology', json.dumps(data))
        self.save_topology()
