from blueprints import BlueprintBase
from nfvo import sol006_VNFbuilder, sol006_NSD_builder, get_ns_vld_ip
from typing import Union, List, Dict, Optional
from .models import *
from .utils import search_for_target_router_in_area, check_network_exists_in_router, check_rule_exists_in_router
from .configurators import Configurator_VyOS
from rest_endpoints.topology import get_topology_item
from main import NbiUtil, create_logger, persistency, osm_user, osm_ip, osm_passwd, osm_port, osm_proj
import traceback
import re

db = persistency.DB()
logger = create_logger('VyOSBlue')
nbiUtil = NbiUtil(username=osm_user, password=osm_passwd, project=osm_proj, osm_ip=osm_ip, osm_port=osm_port)


class VyOSBlue(BlueprintBase):
    vyos_model: VyOSBlueprint

    @classmethod
    def rest_create(cls, msg: VyOSBlueprintCreate):
        return cls.api_day0_function(msg)

    @classmethod
    def rest_snat(cls, msg: VyOSBlueprintSNATCreate, blue_id: str):
        return cls.api_day2_function(msg, blue_id)

    @classmethod
    def rest_dnat(cls, msg: VyOSBlueprintDNATCreate, blue_id: str):
        return cls.api_day2_function(msg, blue_id)

    @classmethod
    def rest_1to1nat(cls, msg: VyOSBlueprintNAT1to1Create, blue_id: str):
        return cls.api_day2_function(msg, blue_id)

    @classmethod
    def rest_nat_delete(cls, msg: VyOSBlueprintNATdelete, blue_id: str):
        return cls.api_day2_function(msg, blue_id)

    @classmethod
    def day2_methods(cls):
        cls.api_router.add_api_route(path="/{blue_id}/snat", endpoint=cls.rest_snat, methods=["PUT"],
                                     description=ADD_SNAT_DESCRIPTION, summary=ADD_SNAT_DESCRIPTION)
        cls.api_router.add_api_route(path="/{blue_id}/1to1nat", endpoint=cls.rest_1to1nat, methods=["PUT"],
                                     description=ADD_1TO1_NAT_DESCRIPTION, summary=ADD_1TO1_NAT_SUMMARY)
        cls.api_router.add_api_route(path="/{blue_id}/dnat", endpoint=cls.rest_dnat, methods=["PUT"],
                                     description=ADD_DNAT_DESCRIPTION, summary=ADD_DNAT_SUMMARY)
        cls.api_router.add_api_route(path="/{blue_id}/nat", endpoint=cls.rest_nat_delete, methods=["DELETE"],
                                     description=DEL_NAT_DESCRIPTION, summary=DEL_NAT_SUMMARY)

    def __init__(self, conf: dict, id_: str, data: Union[Dict, None] = None):
        BlueprintBase.__init__(self, conf, id_, data=data, nbiutil=nbiUtil, db=db)
        logger.info("Creating VyOS Blueprint")
        self.supported_operations = {
            'init': [{
                'day0': [{'method': 'bootstrap_day0'}],
                'day2': [{'method': 'init_day2_conf', 'callback': 'get_interface_info'}]
            }],
            'snat': [{
                'day0': [],
                'day2': [{'method': 'set_snat_rules'}],
                'dayN': []
            }],
            'dnat': [{
                'day0': [],
                'day2': [{'method': 'set_dnat_rules'}],
                'dayN': []
            }],
            '1to1nat': [{
                'day0': [],
                'day2': [{'method': 'set_1to1nat_rules'}],
                'dayN': []
            }],
            'del_nat': [{
                'day0': [],
                'day2': [{'method': 'delete_nat_rules'}],
                'dayN': []
            }]
        }
        self.vnfd = {'area': []}

    def bootstrap_day0(self, msg: dict) -> list:
        self.topology_terraform(msg)
        return self.nsd()

    def get_ip(self):
        """
        This method is used to get IP addresses, assigned by OSM/Openstack, in order to configure the VyOS instances. We
        need this data in order to configure correct IP addresses to routers interfaces.
        The retrived data is then stored inside the model and saved to the DB.
        """
        logger.debug('getting IP addresses from vnf instances')
        for n in self.nsd_:
            management_vld = get_ns_vld_ip(n['nsi_id'], ["mgt"])

            area_iterator: VyOSArea
            config_iterator: VyOSConfig
            target_router: VyOSConfig

            # For each area there is the need to select the right one
            area = next(area_iterator for area_iterator in self.vyos_model.areas if area_iterator.id == n['area'])
            # Each area can have multiple config (that correspond to router), we need to select the right one (The one with nsd name = current nsd)
            target_router = next(config_iterator for config_iterator in area.config_list if
                                 config_iterator.name == n['descr']['nsd']['nsd'][0]['name'])
            target_router.nsd_id = n['nsi_id']

            data_interface_list = []
            for data_network_endpoint in target_router.network_endpoints.data_nets:
                data_interface_list.append(data_network_endpoint.net_name)
            vlds = get_ns_vld_ip(n['nsi_id'], data_interface_list)

            for virtual_link_descriptor_name in vlds:
                for virtual_link_descriptor in vlds[virtual_link_descriptor_name]:
                    target_data_net = next(data_net for data_net in target_router.network_endpoints.data_nets if
                                           data_net.net_name == virtual_link_descriptor['ns_vld_id'])
                    target_data_net.ip_addr = virtual_link_descriptor['ip']
                    target_data_net.osm_interface_name = virtual_link_descriptor['intf_name']
                    self.get_network_cidr(target_data_net)

            # We insert the management ip in the model
            target_router.network_endpoints.mgt.ip_addr = management_vld["mgt"][0]['ip']
            self.get_network_cidr(target_router.network_endpoints.mgt)
        self.to_db()

    def get_network_cidr(self, network: VyOSRouterPortModel):
        """
        Get cidr information of the given Router port and put into the relative object.

        @param network: The port model, connected to a network. The retrieved network's cidr is written inside this object.
        """
        topology_net = get_topology_item('networks', network.net_name)
        if topology_net is not None:
            network.network = topology_net['cidr']

    def topology_terraform(self, msg: dict) -> None:
        """
        Parse the received message into the corresponding model. This is very useful because it is not necessary to
        analyze again the message in next day0 methods.
        Then checks:
        - That a VIM exists for that areas
        - That the management and data networks exist
        - That data networks exist
        It gives a name to the vyos router.
        """
        try:
            logger.debug("Blue {} - terraforming".format(self.get_id()))

            # network_endpoints = []
            areas: dict

            self.vyos_model = VyOSBlueprint.parse_obj(msg)

            # For each area in which we would like to develop a VyOS router we check if it is feasible.
            for area in self.vyos_model.areas:
                logger.debug("Blue {} - checking area {}".format(self.get_id(), area.id))
                # Check if the vim exists
                vim = self.topology_get_vim_by_area(area.id)
                if not vim:
                    raise ValueError('Blue {} - no VIMs at area {}'.format(self.get_id(), area.id))

                config: VyOSConfig
                device_index = 0
                for config in area.config_list:
                    # Setting the name as it is set in the nsd
                    config.name = '{}_vyos_router_area_{}_{}'.format(self.get_id(), area.id, device_index)
                    # Check if the management network exist in the vim. If it does, the network is
                    # added to the list
                    man_network = config.network_endpoints.mgt
                    if man_network.net_name not in vim['networks']:
                        raise ValueError('Blue {} - management network {} not available at VIM {}'
                                         .format(self.get_id(), man_network.net_name, vim['name']))
                    self.get_network_cidr(man_network)

                    # Check if data networks exist in the area managed by the VIM. If it does, the network is
                    # added to the list
                    data_networks = config.network_endpoints.data_nets
                    for data_network in data_networks:
                        if data_network.net_name not in vim['networks']:
                            raise ValueError('Blue {} - management network {} not available at VIM {}'
                                             .format(self.get_id(), data_network, vim['name']))
                        # self.get_network_info(data_network)

                    device_index = device_index + 1

        except Exception:
            logger.error(traceback.format_exc())
            raise ValueError("Terraforming Error")

    def setVnfd(self, area_id: Optional[int] = None, vld: Optional[list] = None,
                vm_flavor_request: Optional[dict] = None, device_number: int = 0) -> None:
        logger.debug("setting VNFd of VyOS for area " + str(area_id))

        vyos_username = 'vyos'  # TODO make then dynamic, and these values for default
        vyos_password = 'vyos'

        vm_flavor = {'memory-mb': '4098', 'storage-gb': '16', 'vcpu-count': '4'}

        # If there is an explicit request for the flavor, we update it
        if vm_flavor_request is not None:
            vm_flavor.update(vm_flavor_request)

        if vld is None:
            # Management interface
            interfaces = [{'vld': 'mgt', 'name': 'ens3', "mgt": True}]
        else:
            interfaces = []
            intf_index = 3  # starting from ens3
            for router_link in vld:
                interfaces.append(
                    {
                        "vld": router_link["vld"],
                        "name": "ens{}".format(intf_index),
                        "mgt": router_link["mgt"],
                        "port-security-enabled": False
                    }
                )
                intf_index += 1

        vnfd = sol006_VNFbuilder(self.nbiutil, self.db, {
            'username': vyos_username,
            'password': vyos_password,
            'id': '{}_vyos_{}_{}'.format(self.get_id(), str(area_id), device_number),
            'name': '{}_vyos_{}_{}'.format(self.get_id(), str(area_id), device_number),
            'vdu': [{
                'count': 1,
                'id': 'VM',
                'image': 'VyOS',
                'vm-flavor': vm_flavor,
                'interface': interfaces
            }]}, charm_name='helmflexvnfm')
        self.vnfd['area'].append(
            {'area_id': area_id, 'vnfd': [{'id': 'vnfd', 'name': vnfd.get_id(), 'vl': interfaces}]})

    def getVnfd(self, area_id: int = None) -> list:
        """Retrieve the virtual network function descriptor of the VyOS instance in the area"""
        if area_id is None:
            raise ValueError("area is None in getVnfd")
        # Takes the area that correspond to the area id
        area_obj = next((item for item in self.vnfd['area'] if item['area_id'] == area_id), None)
        if area_obj is None:
            raise ValueError("area not found in getting Vnfd")
        return area_obj['vnfd']

    def vyos_router_nsd(self, area_id: int, target_config: VyOSConfig, device_number: int):
        """
        Build a vyos router NSD.
        The NSD is build starting from the message request.
        @param area_id: The area where the vyos is going to be deployed
        @param target_config: the configuration of the vyos router to be deployed
        @param device_number: The device number is used to distinguish routers in the same area of interest (should be
        incremental for each config).
        """
        logger.info("Building VyOS router NSD")

        param = {
            'name': '{}_vyos_router_area_{}_{}'.format(self.get_id(), area_id, device_number),
            'id': '{}_vyos_router_area_{}_{}'.format(self.get_id(), area_id, device_number),
            'type': 'VyOSBlue'
        }

        # Saving the nsd name into the configuration such that it is possible, in day2 config, to connect nsd to router config
        target_config.nsd_name = param['name']

        mng_net = target_config.network_endpoints.mgt.net_name
        vim_net_mapping = [
            {'vld': 'mgt', 'vim_net': mng_net, "mgt": True}
        ]

        # Connecting the vyos router to all endpoints present in the request
        for data_endpoint in target_config.network_endpoints.data_nets:
            if data_endpoint.net_name != vim_net_mapping[0]['vim_net']:
                vim_net_mapping.append(
                    {'vld': '{}'.format(data_endpoint.net_name), 'vim_net': data_endpoint.net_name, "mgt": False}
                )

        if not target_config.vyos_router_flavors:
            vm_flavor = None
        else:
            vm_flavor = target_config.vyos_router_flavors.copy()

        self.setVnfd(area_id, vld=vim_net_mapping, vm_flavor_request=vm_flavor, device_number=device_number)

        n_obj = sol006_NSD_builder(
            self.getVnfd(area_id), self.get_vim_name(area_id), param, vim_net_mapping)

        n_ = n_obj.get_nsd()
        n_['area'] = area_id
        n_['device_number'] = device_number
        self.nsd_.append(n_)
        return param['name']

    def nsd(self) -> List[str]:
        """
        Build and return a list of Network Service Descriptor.
        For each router in each area a new NSD is built and added to the list to be returned.

        @return nsd names list
        """
        logger.info("Creating VyOS Network Service Descriptors")
        nsd_names = []
        # We create a NSD for each service, in particular for each VyOS instance
        # We can use self.conf['areas'] because when the base blueprint has been instantiated
        # it has already parsed the data (see constructor)

        for area in self.vyos_model.areas:
            # Each config coorespond to a Network service
            device_number = 0
            for vyos_configuration in area.config_list:
                logger.info(
                    "Blue {} - Creating VyOS instance Service Descriptors on area {}".format(self.get_id(), area.id))
                nsd_names.append(self.vyos_router_nsd(area.id, vyos_configuration, device_number))
                device_number = device_number + 1

        logger.info("NSDs created")
        return nsd_names

    def init_day2_conf(self, msg) -> list:
        """
        For each instantiated network service, this method spawns a VYOS configurator that generates the required
        playbook needed by the virtual network manager to configure correctly the interfaces (based on the ip addresses
        assigned by osm and openstack to the vyos router instance
        """
        logger.debug("Triggering Day2 Config for VyOS blueprint " + str(self.get_id()))
        res = []
        for nsd_item in self.nsd_:
            area: VyOSArea
            # We need to look witch router correspond to this nsd
            # We need to look inside at each area for every router config
            for area in self.vyos_model.areas:
                router_config: VyOSConfig
                # For each area we can have different routers
                for router_config in area.config_list:
                    # Checking the router that correspond to this nsd
                    if router_config.nsd_name == nsd_item['descr']['nsd']['nsd'][0]['id']:
                        network_endpoints_for_router = router_config.network_endpoints
                        if network_endpoints_for_router is None:
                            raise ValueError('Blue {} - No network_endpoints for router {} has been found!'.format(
                                self.vyos_model.blueprint_instance_id, router_config.name))

                        ## TODO Save configurator in the object. Right now it is not possible cause configurator in not
                        # compatible with pydantic. So we need to create it every time
                        # Once we have found the corresponding router, we can spawn the configurator
                        vyos_configurator = Configurator_VyOS(
                            area_id=area.id,
                            nsd_name=nsd_item['descr']['nsd']['nsd'][0]['id'],
                            m_id=1,
                            blue_id=self.get_id(),
                            network_endpoints=network_endpoints_for_router
                        )
                        vyos_configurator.initial_configuration()

                        res += vyos_configurator.dump()
        # Saving self to database
        self.to_db()
        return res

    def set_snat_rules(self, msg: dict, request: VyOSBlueprintSNATCreate = None):
        """
        Message handler for SNAT rule addition in a VyOS Router
            -Parse the model if it is not present (Only self.conf is saved in DB, NOT self.vyos_model)
            -It search for the corresponding router in the specified area
            -Check if the specified interfaces nameS exist on that router (for each rule)
            -Build a configurator in order to apply the rules
            -Return primitive to be executed
        """
        if not self.vyos_model:
            self.vyos_model = VyOSBlueprint.parse_obj(self.conf)
        if not request:
            request = VyOSBlueprintSNATCreate.parse_obj(msg)

        target_router: VyOSConfig
        target_area, target_router = search_for_target_router_in_area(area_list=self.vyos_model.areas,
                                                                      target_area_id=request.area,
                                                                      target_router_name=request.router_name)
        primitives_to_exec = []
        rule: VyOSSourceNATRule
        for rule in request.rules:
            # Checking if the interface exists.
            target_outbound_network = check_network_exists_in_router(target_network_addr=rule.outbound_network,
                                                                     target_router_config=target_router)
            rule.outbound_interface = target_outbound_network.interface_name

        # Creating the configurator for deploying the ruleS
        vyos_configurator = Configurator_VyOS(
            area_id=target_area.id,
            nsd_name=target_router.nsd_name,
            m_id=1,
            blue_id=self.get_id()
        )
        vyos_configurator.setup_snat_rules(request.rules)

        primitives_to_exec.extend(vyos_configurator.dump())

        target_router.extend_snat_rules(request.rules)

        self.to_db()

        return primitives_to_exec

    def set_dnat_rules(self, msg: dict, request: VyOSBlueprintDNATCreate = None):
        """
        Message handler for DNAT rule addition in a VyOS Router
            -Parse the model if it is not present (Only self.conf is saved in DB, NOT self.vyos_model)
            -It search for the corresponding router in the specified area of the blueprint
            -Check if the specified interfaces name exist on that router (for each rule)
            -Build a configurator in order to apply the rules
            -Return primitive to be executed
        """
        if not self.vyos_model:
            self.vyos_model = VyOSBlueprint.parse_obj(self.conf)
        if not request:
            request = VyOSBlueprintDNATCreate.parse_obj(msg)

        target_router: VyOSConfig
        target_area, target_router = search_for_target_router_in_area(area_list=self.vyos_model.areas,
                                                                      target_area_id=request.area,
                                                                      target_router_name=request.router_name)

        primitives_to_exec = []
        rule: VyOSDestNATRule
        for rule in request.rules:
            # Checking if the interface exists.
            target_outbound_network = check_network_exists_in_router(target_network_addr=rule.inbound_network,
                                                                     target_router_config=target_router)
            rule.inbound_interface = target_outbound_network.interface_name

        # Creating the configurator for deploying the ruleS
        vyos_configurator = Configurator_VyOS(
            area_id=target_area.id,
            nsd_name=target_router.nsd_name,
            m_id=1,
            blue_id=self.get_id()
        )
        vyos_configurator.setup_dnat_rules(request.rules)

        primitives_to_exec.extend(vyos_configurator.dump())

        target_router.extend_dnat_rules(request.rules)

        self.to_db()

        return primitives_to_exec

    def set_1to1nat_rules(self, msg: VyOSBlueprintNAT1to1Create):
        """
        This method is the handler for NAT 1 to 1 handler.
        The rule is composed by a DNAT rule and a SNAT rule with a particular form.
        """
        if not self.vyos_model:
            self.vyos_model = VyOSBlueprint.parse_obj(self.conf)
        snat_msg = msg.copy()
        snat_msg.operation = 'snat'
        dnat_msg = msg.copy()
        dnat_msg.operation = 'dnat'

        snat_request = VyOSBlueprintSNATCreate.parse_obj(snat_msg)
        dnat_request = VyOSBlueprintDNATCreate.parse_obj(dnat_msg)

        primitives_to_exec = []
        primitives_to_exec.extend(self.set_snat_rules(msg=msg, request=snat_request))
        primitives_to_exec.extend(self.set_dnat_rules(msg=msg, request=dnat_request))

        return primitives_to_exec

    def get_interface_info(self, callback_msg):
        """
        Setup interface names for each endpoint. The names are retrieved from the result of execution of the setup playbook.
        If the interface is not correctly configured it should NOT appear in the action output of the playbook and then
        here the name is not set because the interface have NO ip address.
        The interface eth0 should be always the management interface.
        Before assigning the name to an interface, this method checks that the IP of the network interface correspond to
        the one assigned by OSM/OPENSTACK.
        """
        for primitive in callback_msg:
            if primitive['result']['charm_status'] != 'completed':
                raise ValueError('in k8s blue -> get_master_key callback charm_status is not completed')

            target_router: VyOSConfig = None
            router_config: VyOSConfig = None
            # Looking for the corresponding router
            for area in self.vyos_model.areas:
                for router_config in area.config_list:
                    if router_config.nsd_name == primitive['primitive']['ns-name']:
                        target_router = router_config
                        break
                if target_router is not None:
                    break
            if target_router is None:
                raise ValueError("NSD corresponding router was not found!")

            action_id = primitive['primitive']['primitive_data']['primitive_params']['config-content']['action_id']

            action_output = db.findone_DB('action_output', {'action_id': action_id})

            # There should be only one playbook
            playbook = action_output['result'][0]
            # There should be only one play inside the playbook
            first_play = playbook['stdout']['plays'][0]
            # The last task should be the one collecting L3 information (see configurator)
            last_index = len(first_play['tasks'])
            hosts = first_play['tasks'][last_index - 1]['hosts']
            # There is one host called "host" (see configurator, in particular the playbook template)
            gathered_info = hosts['host']['gathered']

            for element in gathered_info:
                if element['name'] == 'eth0':
                    router_config.network_endpoints.mgt.interface_name = element['name']
                else:
                    match = re.match(r"([a-z]+)([0-9]+)", element['name'], re.I)
                    if match:
                        items = match.groups()
                        interface_number: int = int(items[1])
                        ip_no_mask = element['ipv4'][0]['address'].split("/", 1)[0]
                        if ip_no_mask != router_config.network_endpoints.data_nets[interface_number - 1].ip_addr:
                            raise ValueError(
                                "The IP assigned to the vyos port does not correspond to correct IP address")
                        else:
                            router_config.network_endpoints.data_nets[interface_number - 1].interface_name = element[
                                'name']
                    else:
                        raise ValueError("Error parsing the interface name during vyos configuration callback")
        self.to_db()

    def delete_nat_rules(self, msg: VyOSBlueprintNATdelete):
        """
        This method is the handler for NAT delete request.
        - Looks for the target router of the blueprint instance
        - Makes a list of rules to delete. NB if the rule 16 has to be deleted, both SNAT and DNAT rules 16 will be
            deleted
        - Build a configurator to create the primitive to be executed on the real VyOS instance
        - Delete the rule from the model
        - return the primitive
        """
        if not self.vyos_model:
            self.vyos_model = VyOSBlueprint.parse_obj(self.conf)
        request: VyOSBlueprintNATdelete = VyOSBlueprintNATdelete.parse_obj(msg)

        target_router: VyOSConfig
        target_area, target_router = search_for_target_router_in_area(area_list=self.vyos_model.areas,
                                                                      target_area_id=request.area,
                                                                      target_router_name=request.router_name)

        primitives_to_exec = []
        snat_rule_list: List[VyOSSourceNATRule] = []
        dnat_rule_list: List[VyOSDestNATRule] = []
        rule: VyOSDestNATRule
        for rule_number in request.rules:
            # Checking if the rule exists. ONLY ONE SNAT RULE AND ONE DNAT RULE CAN CORRESPOND TO A RULE NUMBER
            snat_rule, dnat_rule = check_rule_exists_in_router(rule_number=rule_number,
                                                               target_router_config=target_router)
            if snat_rule:
                snat_rule_list.append(snat_rule)
            if dnat_rule:
                dnat_rule_list.append(dnat_rule)

        # Creating the configurator for deploying the ruleS
        vyos_configurator = Configurator_VyOS(
            area_id=target_area.id,
            nsd_name=target_router.nsd_name,
            m_id=1,
            blue_id=self.get_id()
        )

        vyos_configurator.delete_nat_rule(snat_rule_list, dnat_rule_list)

        primitives_to_exec.extend(vyos_configurator.dump())

        target_router.remove_snat_rules(snat_rule_list)
        target_router.remove_dnat_rules(dnat_rule_list)

        self.to_db()

        return primitives_to_exec

    def to_db(self):
        """
        @override
        This method is used to save the model inside the self.conf variable. This workaround is needed because otherwise
        the vyos model is not saved, and the conf var is a useless dict.
        """
        val = getattr(self, 'vyos_model', None)

        if val:
            # If the model is loaded from the db, then we assign to self.conf and call the super method. In this way
            # the model will be saved in the db
            self.conf = self.vyos_model.dict()
        else:
            # If the blueprint instance is loaded for the first time, then the model is empty, and we can parse the
            # dictionary into the model
            self.vyos_model = VyOSBlueprint.parse_obj(self.conf)
        # To save the data (in particular the self.conf variable) we call the super method
        super(VyOSBlue, self).to_db()

    def _destroy(self):
        pass
