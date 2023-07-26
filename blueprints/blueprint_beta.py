import json
import datetime
import requests
import traceback
import importlib
import abc
from models.blueprint.blueprint_base_model import BlueprintBaseModel, BlueNSD, BlueprintVersion
from models.blueprint.rest_blue import BlueGetDataModel, ShortBlueModel
from models.k8s.blue_k8s_model import LBPool
from models.network import NetworkModel
from nfvo import nsd_build_package, NbiUtil
from utils.prometheus_manager import PrometheusMan
from models.blueprint.blue_types import blueprint_types
from typing import List, Dict, Union, Callable
from fastapi import APIRouter
from topology.topology import Topology
from utils import persistency, create_logger


_db = persistency.DB()

# create logger
logger = create_logger('blueprint')


class BlueprintBaseBeta(abc.ABC):
    base_model: BlueprintBaseModel
    api_router: APIRouter
    api_day0_function: Callable
    api_day2_function: Callable

    @classmethod
    @abc.abstractmethod
    def rest_create(cls, msg):
        pass

    @classmethod
    @abc.abstractmethod
    def day2_methods(cls):
        pass

    @classmethod
    def fastapi_router(cls, _day0_func: Callable, _day2_func: Callable):
        cls.api_day0_function = _day0_func
        cls.api_day2_function = _day2_func
        cls.api_router = APIRouter(
            prefix="/{}".format(cls.__name__),
            tags=["Blueprint {}".format(cls.__name__)],
            responses={404: {"description": "Not found"}}
        )
        cls.api_router.add_api_route("", cls.rest_create, methods=["POST"])
        cls.day2_methods()
        return cls.api_router

    def __init__(self, conf: dict, id_: str, data: Union[Dict, None] = None, db: persistency.DB = None,
                 nbiutil: NbiUtil = None):
        if data:
            self.base_model = BlueprintBaseModel.parse_obj(data)
        else:
            data = {}
            conf["blueprint_instance_id"] = id_
            blue_type = self.__class__.__name__
            data["type"] = blue_type
            data['conf'] = conf
            data['id'] = id_
            data['input_conf'] = conf
            self.base_model = BlueprintBaseModel.parse_obj(data)

        self.base_model.version = BlueprintVersion.ver2_00
        self.topology_lock = None
        self.osm_nbiutil = nbiutil
        self.db = db

    @classmethod
    def from_db(cls, blue_id: str):
        """
        Return a blueprint loaded from the database. If the blueprint type is not recognized, then an error is thrown.

        Args:
            blue_id: The ID of the blueprint in the database to be loaded.

        Returns:
            The loaded blueprint in its object form.
        """
        db_data = _db.findone_DB("blueprint-instances", {'id': blue_id})
        if not db_data:
            raise ValueError('blueprint {} not found in DB or malformed'.format(blue_id))
        type = db_data['conf']['type']
        if type not in blueprint_types:
            raise ValueError('type {} for blueprint {} not found'.format(type, blue_id))
        blue_class = blueprint_types[type]
        try:
            return getattr(importlib.import_module("blueprints." + blue_class['module_name']),
                           blue_class['class_name'])(db_data['conf'], blue_id, data=db_data)
        except Exception:
            logger.error(traceback.format_exc())
            raise ValueError('re-initialization for blueprint {} of type {} failed'
                             .format(blue_id, db_data['type']))

    def delete_db(self):
        self.db.delete_DB("action_output", {'blue_id': self.base_model.id})
        self.db.delete_DB("blueprint-instances", {'id': self.base_model.id})

    def to_db(self):
        self.base_model.modified = datetime.datetime.now()
        # self.base_model.dict() is NOT working, some fields remain object
        data_serialized = json.loads(self.base_model.json(by_alias=True))
        if self.db.exists_DB("blueprint-instances", {'id': self.base_model.id}):
            self.db.update_DB("blueprint-instances", data_serialized, {'id': self.base_model.id})
        else:
            self.db.insert_DB("blueprint-instances", data_serialized)

    def get_id(self) -> str:
        """
        Return the blueprint ID

        Returns: the blueprint ID
        """
        return self.base_model.id

    def set_topology_lock(self, topo_lock) -> None:
        self.topology_lock = topo_lock

    def get_operation_methods(self, operation: str) -> List[Dict[str, List]]:
        return self.base_model.supported_operations.get(operation) if hasattr(self.base_model, "supported_operations") \
            else []

    def get_supported_operations(self) -> List[str]:
        if hasattr(self.base_model, "supported_operations"):
            return list(self.base_model.supported_operations.keys())
        else:
            return []

    def build_packages(self, nsd_names) -> list:
        logger.info("Blue {} - Building " + str(len(self.base_model.nsd_)) + " nsd package".format(self.get_id()))
        res = []
        for nsd in self.base_model.nsd_:
            logger.debug("NSD status: {}".format(nsd.status))
            name = nsd.descr.nsd.nsd[0].name

            if name not in nsd_names:
                continue

            if nsd.status != 'day0':
                logger.error("Blue {} -  the state of nsd {} is {}: aborting !"
                             .format(self.get_id(), name, nsd.status))
                raise ValueError('NSD {} not in Day0 state'.format(name))

            nsd_build_package(name, nsd.descr.dict(by_alias=True))
            res.append(name)
        return res

    def get_osm_ns_byname(self, name) -> BlueNSD:
        """
        Return OSM network service given the service name.
        Args:
            name: the name to look for

        Returns:
            The corresponding network service.
        """
        nsd: BlueNSD
        for nsd in self.base_model.nsd_:
            n_descr = nsd.descr.nsd.nsd[0]
            if n_descr.name == name:
                return nsd
        return None

    def add_osm_nsd(self, name: str, ns_id: str):
        """
        Add NSD ID to the NS of the blueprint. Check that the NS with the given name exists.
        Args:
            name: the name of the NS to witch the ID will be added.
            ns_id: The ID to be given at the NS.

        Returns:
            True if the ID is given to the NS

        Raises:
            ValueError
        """
        nsd: BlueNSD = self.get_osm_ns_byname(name)
        if nsd is None:
            raise ValueError('Blueprint NSD not found')
        nsd.nsd_id = ns_id
        return True

    def add_osm_nsi(self, name, ns_id):
        """
        Add network service ID to the network service descriptor
        Args:
            name: The name of the network service
            ns_id: The ID to be added to the network service

        Returns:
            True if the ID has been assigned

        Raises:
            ValueError id NSD not found
        """
        nsd: BlueNSD = self.get_osm_ns_byname(name)
        if nsd is None:
            raise ValueError('Blueprint NSD not found')
        nsd.nsi_id = ns_id
        return True

    def print_detailed_summary(self) -> dict:
        """
        Prints the detailed summary of the blueprint
        """
        #for p in _prims:
        #    p.update({'time': p['time'].strftime("%m/%d/%Y, %H:%M:%S")})
        #    logger.debug(p)
        #    res['primitives'].append(p)
        return self.base_model.dict()

    def print_short_summary(self) -> ShortBlueModel:
        return ShortBlueModel.parse_obj(self.base_model.dict())

    def get_nsd(self) -> List[BlueNSD]:
        """
        Return the LIST of network service descriptors

        Returns:
            the LIST of network service descriptors
        """
        return self.base_model.nsd_

    def set_osm_status(self, name: str, status: str) -> bool:
        """
        Set the status of an OSM Network Service. The status should be taken from osm
        Args:
            name: the NS name to witch the status is assigned

            status: the status to be assigned

        Returns:
            True if the status has been set. False if the NS has not been found.
        """
        nsd: BlueNSD
        for nsd in self.base_model.nsd_:
            nsd_name = nsd.descr.nsd.nsd[0].name

            if nsd_name == name:
                nsd.status = status
                self.to_db()
                return True
        logger.error("[ERROR] blueprint ns not found")
        return False

    def deploy_config(self, nsd_id: str):
        """
        Retrieve the deployment configuration of the NSD given the ID
        Args:
            nsd_id: The ID of the NS

        Returns:
            The deployment configuration
        """
        ns = next((network_service for network_service in self.base_model.nsd_ if network_service.nsd_id == nsd_id), None)
        if ns is None:
            raise ValueError('NSD with id ' + nsd_id + ' not present in blueprint')
        if getattr(ns, 'deploy_config', None) is None:
            return None
        else:
            return ns.deploy_config.dict(by_alias=True)  # For compatibility with OSM nbi utils

    def get_vnf_data(self):
        """
        Gets (Updates) the VNF instances data from OSM.

        Todo:
            - add kdus and pdus
        """
        # Resetting the vnfi to be updated from OSM
        self.base_model.vnfi = []
        self.base_model.deployment_units = []

        # Getting all the vnf instances for the blueprint's network services from OSM
        nsi_ids = [item.nsd_id for item in self.base_model.nsd_]
        for nsi in nsi_ids:
            self.base_model.vnfi += self.osm_nbiutil.get_vnfi_list(nsi)

        for vnf in self.base_model.vnfi:
            for du in vnf['vdur']:
                self.base_model.deployment_units.append({
                    'name': du['name'],
                    'vnfd-name': vnf['vnfd-ref'],
                    'ns_id': vnf['nsr-id-ref'],
                    'member-vnf-index-ref': vnf['member-vnf-index-ref'],
                    'ip-address': du['ip-address'],
                    'status': du['status'],
                    'type': 'vdu'
                })

    @abc.abstractmethod
    def get_ip(self):
        pass

    @abc.abstractmethod
    def get_data(self, get_request: BlueGetDataModel):
        pass

    def topology_add_pdu(self, pdu: dict):
        """
        Add a PDU to the topology
        Args:
            pdu: The PDU to be added
        """
        topology = Topology.from_db(self.db, self.osm_nbiutil, self.topology_lock)
        topology.add_pdu(pdu)
        topology.save_topology()
        self.base_model.pdu.append(pdu['name'])

    def topology_del_pdu(self, pdu_name: str):
        """
        Delete a PDU from the topology and then from this blueprint instance
        Args:
            pdu_name: The name of the PDU to be deleted
        """
        # Removing from the topology
        topology = Topology.from_db(self.db, self.osm_nbiutil, self.topology_lock)
        topology.del_pdu(pdu_name)
        # Removing from this blueprint
        self.base_model.pdu = [item for item in self.base_model.pdu if item != pdu_name]

    def topology_get_pdu(self, pdu_name: str):
        """
        Retrieve a PDU from the topology
        Args:
            pdu_name: The name of the PDU to be retrieved
        """
        topology = Topology.from_db(self.db, self.osm_nbiutil, self.topology_lock)
        return topology.get_pdu(pdu_name)

    def topology_get_pdu_by_area(self, area_id):
        """
        Retrieve the FIRST PDU from the topology by area
        
        Args:
            area_id: the area in witch the function is looking for the PDU
        """
        topology = Topology.from_db(self.db, self.osm_nbiutil, self.topology_lock)
        pdus = topology.get_pdus()
        if type(area_id) is dict:
            return next((item for item in pdus if item['area'] == area_id['id']), None)
        else:
            return next((item for item in pdus if item['area'] == area_id), None)

    def topology_get_pdu_by_area_and_type(self, area_id: str, pdu_type: str) -> dict:
        """
        Retrieve the **FIRST** PDU from the topology by area and by type

        Args:
            area_id: the area in witch the function is looking for the PDU
            
            pdu_type: the type of the PDU
        """
        topology = Topology.from_db(self.db, self.osm_nbiutil, self.topology_lock)
        pdus = topology.get_pdus()
        return next((item for item in pdus if item['area'] == area_id and item['type'] == pdu_type), None)

    def topology_get_vim_by_area(self, area_id):
        """
        Retrieve the **FIRST** VIM from the topology by area

        Args:
            area_id: the area in witch the function is looking for VIM
        """
        topology = Topology.from_db(self.db, self.osm_nbiutil, self.topology_lock)
        if type(area_id) is dict:
            return topology.get_vim_from_area_id(area_id['id'])
        else:
            return topology.get_vim_from_area_id(area_id)

    def topology_add_k8scluster(self, k8s_cluster_data: dict):
        """
        Add a K8S cluster to the topology

        Args:
            k8s_cluster_data: the K8S cluster in dictionary form to be added to the topology
        """
        topology = Topology.from_db(self.db, self.osm_nbiutil, self.topology_lock)
        topology.add_k8scluster(k8s_cluster_data)

    def topology_del_k8scluster(self):
        """
        Delete the K8S cluster, with ID that is corresponding to this blueprint ID, from the topology.
        """
        topology = Topology.from_db(self.db, self.osm_nbiutil, self.topology_lock)
        topology.del_k8scluster(self.get_id())

    def topology_update_k8scluster(self, k8s_cluster_data: dict):
        """
        Update the K8S cluster, with ID that is corresponding to this blueprint ID, in the topology.

        Args:
            k8s_cluster_data: the data to be used to update the K8s cluster
        """
        topology = Topology.from_db(self.db, self.osm_nbiutil, self.topology_lock)
        topology.update_k8scluster(self.get_id(), k8s_cluster_data)
        topology.save_topology()

    def topology_add_network(self, net: NetworkModel, areas: list):
        """
        Add network to the topology and

        Args:
            net: the network to be added in the topology

            areas: area ID used to retrieve the VIMs. The network is then added to every VIM in the list (terraform
            is set to true)
        """
        topology = Topology.from_db(self.db, self.osm_nbiutil, self.topology_lock)
        vims = set()
        for a in areas:
            if type(a) == int:
                vims.add(topology.get_vim_name_from_area_id(a))
                logger.debug("for area {} the following vims have been selected: {}".format(a, vims))
            else:
                vims.add(topology.get_vim_name_from_area_id(a['id']))
                logger.debug("for area {} the following vims have been selected: {}".format(a['id'], vims))
        topology.add_network(net, list(vims), terraform=True)
        topology.save_topology()

    def topology_del_network(self, net: NetworkModel, areas: Union[List[int], List[dict]]):
        """
        Delete network from the topology and then remove it from every VIM of the area (terraform is set to true)

        Args:

            net: the network to be added in the topology

            areas: area ID list used to retrieve the VIM list. The network is removed from every VIM.
        """
        topology = Topology.from_db(self.db, self.osm_nbiutil, self.topology_lock)
        vims = set()
        for area in areas:
            if type(area) == int:
                vims.add(topology.get_vim_name_from_area_id(area))
                logger.debug("Blue {} - for area {} the following vims have been selected: {}"
                             .format(self.get_id(), area, vims))
            elif type(area) == dict:
                vims.add(topology.get_vim_name_from_area_id(area['id']))
                logger.debug("Blue {} - for area {} the following vims have been selected: {}"
                             .format(self.get_id(), area['id'], vims))
            else:
                raise ValueError("Type error in areas")
        topology.del_network(net, list(vims), terraform=True)
        topology.save_topology()

    def topology_get_network(self, network_name: str) -> NetworkModel:
        """
        Return a network from the topology.

        Args:
            network_name: The name of the network to be returned

        Returns:
            The network
        """
        topology = Topology.from_db(self.db, self.osm_nbiutil, self.topology_lock)
        net_dict = topology.get_network(network_name)  # TODO avoid parsing object when topology will be updated
        return NetworkModel.parse_obj(net_dict)

    def topology_reserve_ip_range(self, lb_pool: LBPool):
        """
        Reserve an IP range in the topology with owner that is this blueprint ID.

        Args:
            lb_pool: the pool to be reserved

        Returns:
            The reserved IP range -> {'start': '192.168.0.1', 'end': '192.168.0.100'}
        """
        topology = Topology.from_db(self.db, self.osm_nbiutil, self.topology_lock)
        return topology.reserve_range(lb_pool.net_name, lb_pool.range_length, self.get_id())

    def topology_release_ip_range(self):
        """
        Delete the reserved IP range in the topology that has this blueprint ID as owner

        Returns:
            The reserved IP range -> {'start': '192.168.0.1', 'end': '192.168.0.100'}
        """
        topology = Topology.from_db(self.db, self.osm_nbiutil, self.topology_lock)
        return topology.release_ranges(self.get_id())

    def get_vim_name(self, area: Union[int, dict]) -> str:
        """
        Returns the name of the FIRST matching VIM, given the area of interest.
        Args:
            area: the area in witch the vim is searched. Can be both 'int' ID or dictionary with 'id' key containing the
            area ID.

        Returns:
            The name FIRST matching VIM for that area
        """
        topology = Topology.from_db(self.db, self.osm_nbiutil, self.topology_lock)
        if type(area) == int:
            return topology.get_vim_name_from_area_id(area)
        else:
            return topology.get_vim_name_from_area_id(area['id'])

    def get_vim(self, area: Union[int, dict]) -> dict:
        """
        Returns the FIRST VIM, given the area of interest.
        Args:
            area: the area in witch the vim is searched. Can be both 'int' ID or dictionary with 'id' key containing the
            area ID.

        Returns:
            The FIRST matching VIM for that area
        """
        topology = Topology.from_db(self.db, self.osm_nbiutil, self.topology_lock)
        if type(area) == int:
            return topology.get_vim_from_area_id(area)
        else:
            return topology.get_vim_from_area_id(area['id'])

    def get_vims(self):
        """
        For each area takes the FIRST VIM and add it to a list to be returned.

        Returns:
            A list of VIM, one for each deployment area.
        """
        deployment_areas = set()
        for area in self.base_model.conf['areas']:
            deployment_areas.add(area) if type(area) is int else deployment_areas.add(area['id'])

        vims_names = set()
        vims = []
        topology = Topology.from_db(self.db, self.osm_nbiutil, self.topology_lock)
        for area in deployment_areas:
            area_vim = topology.get_vim_from_area_id(area)
            if area_vim['name'] not in vims_names:
                vims_names.add(area_vim['name'])
                vims.append(area_vim)
        return vims

    def destroy(self):
        """
        Destroy the blueprint.
        Delete PDUs
        Call child _destroy function.
        Delete itself from the Database.
        Returns:
        """
        logger.info("Destroying")
        if hasattr(self, "pdu"):
            for p in self.pdu:
                logger.debug("deleting pdu {}".format(p))
                self.topology_del_pdu(p)
        self._destroy()
        self.delete_db()

    @abc.abstractmethod
    def _destroy(self):
        """
        Function that needs to be implemented in child blueprints to when a blueprint is destroyed.
        """
        pass

    def delete_nsd(self, nsi: str):
        """
        Delete NSD from the blueprint

        Args:
            nsi: The identifier of the network service to be deleted
        """
        nsd: BlueNSD
        res = [nsd for nsd in self.base_model.nsd_ if 'nsi_id' in nsd and not (nsd.nsd_id == nsi)]
        self.base_model.nsd_ = res
        self.to_db()

    def set_timestamp(self, label: str, tstamp: datetime.datetime = None) -> None:
        """
        Set the timestamp value relative to the given label.
        Args:
            label: The label of the timestamp
            tstamp: The timestamp value to be set with the give label

        Returns:
            The set value
        """
        self.base_model.timestamp[label] = tstamp if tstamp else datetime.datetime.now()
        return self.base_model.timestamp[label]

    def get_performance(self):
        result = {'blueprint_id': self.get_id(), 'blueprint_type': self.base_model.type,
                  'start_time': self.base_model.timestamp['day0_start'].strftime("%H:%M:%S.%f"), 'measures': []}
        for key, value in self.base_model.timestamp.items():
            # HERE config len - check label
            if key != 'day0_start':
                delta = value - self.base_model.timestamp['day0_start']
                result['measures'].append({'label': key, 'duration': int(delta.total_seconds() * 1000), 'unit': 'ms'})
        for key, value in self.base_model.config_len.items():
            for r in result['measures']:
                if r['label'] == key:
                    r['config_len'] = value

        return result

    def set_configlen(self, label, config):
        """
        Set the config len with the specified label
        Args:
            label: the label to be used in the config_len dictionary
            config: The config on witch the len is calculated

        Returns:
            The set config len value
        """
        self.base_model.config_len[label] = len(json.dumps(config))
        return self.base_model.config_len[label]

        #def findNsdTemplate(self, category_, type_, flavors_):
        #templates = db.find_DB(
        #    "nsd_templates", {'category': category_, 'type': type_})
        #n_ = next((item for item in templates if (set(flavors_['include']) <= set(
        #    item['flavors'])) and not bool(set(flavors_['exclude']) & set(item['flavors']))), None)
        #if n_ is None:
        #    raise ValueError('NSD template not found in the catalogue')
        #return n_['descriptor']

    @staticmethod
    def updateVnfdNames(vnfd_names, nsd_):
        """
        Updates names of VNFD in blueprint NSDs.
        
        Args:
            vnfd_names: a List of dictionaries containing 'id' and 'name' values. The 'name' is used to update a VNFD 
            when 'id' is mathing one of the VNFD.
            
            nsd_: the LIST of network service descriptors in witch the VNFDs are updated.

        Returns:
            The updated NSD list.
        """
        for v in vnfd_names:
            for ref in nsd_['constituent-vnfd']:
                if ref['vnfd-id-ref'] == v['id']:
                    ref['vnfd-id-ref'] = v['name']
            for link in nsd_['vld']:
                for ref in link['vnfd-connection-point-ref']:
                    if ref['vnfd-id-ref'] == v['id']:
                        ref['vnfd-id-ref'] = v['name']
        return nsd_

    def enable_elk(self, args):
        # NOTE check if the Blue is in "day2" status
        res = []
        if "vnf_type" in args:
            for configurator in self.base_model.vnf_configurator:
                if configurator.blue_type() == args["vnf_type"]:
                    res.append(configurator.enable_elk(args)[-1])
            return res
        elif "ns_type" in args:
            for nsd in self.base_model.nsd_:
                if nsd.type == args["ns_type"]:
                    for configurator in self.base_model.vnf_configurator:
                        if configurator.nsd_id == nsd.nsd_id:
                            res.append(configurator.enable_elk(args)[-1])
            return res
        elif "nsi_id" in args:
            for nsd in self.base_model.nsd_:
                if nsd.nsi_id == args["nsi_id"]:
                    for configurator in self.base_model.vnf_configurator:
                        if configurator.nsd_id == nsd.nsd_id:
                            res.append(configurator.enable_elk(args)[-1])
            return res
        elif "nsd_id" in args:
            for nsd in self.base_model.nsd_:
                if nsd.nsd_id == args["nsd_id"]:
                    for configurator in self.base_model.vnf_configurator:
                        if configurator.nsd_id == nsd.nsd_id:
                            if "vnfd_id" in args:
                                if configurator.nsd['member-vnfd-id'] == args["vnfd_id"]:
                                    res.append(configurator.enable_elk(args)[-1])
                            else:
                                res.append(configurator.enable_elk(args)[-1])
        else:
            for configurator in self.base_model.vnf_configurator:
                res.append(configurator.enable_elk(args)[-1])

        return res

    def enable_prometheus(self, args):
        # TODO check if it is used and working
        # global PrometheusMan
        # NOTE check if the Blue is in "day2" status
        res = []
        if "vnf_type" in args:
            for configurator in self.base_model.vnf_configurator:
                if configurator.blue_type() == args["vnf_type"]:
                    res.append(configurator.enable_prometheus(args)[-1])
            return res
        elif "ns_type" in args:
            for nsd in self.base_model.nsd_:
                if nsd.type == args["ns_type"]:
                    for configurator in self.base_model.vnf_configurator:
                        if configurator.nsd_id == nsd.nsd_id:
                            res.append(configurator.enable_prometheus(args)[-1])
            return res
        elif "nsi_id" in args:
            for nsd in self.base_model.nsd_:
                if nsd.nsi_id == args["nsi_id"]:
                    for configurator in self.base_model.vnf_configurator:
                        if configurator.nsd_id == nsd.nsd_id:
                            res.append(configurator.enable_prometheus(args)[-1])
            return res
        elif "nsd_id" in args:
            for nsd in self.base_model.nsd_:
                if nsd.nsd_id == args["nsd_id"]:
                    for configurator in self.base_model.vnf_configurator:
                        if configurator.nsd_id == nsd.nsd_id:
                            if "vnfd_id" in args:
                                if configurator.nsd['member-vnfd-id'] == args["vnfd_id"]:
                                    res.append(configurator.enable_prometheus(args)[-1])
                            else:
                                res.append(configurator.enable_prometheus(args)[-1])
        else:
            for configurator in self.base_model.vnf_configurator:
                res.append(configurator.enable_prometheus(args)[-1])
        PrometheusMan.transferFile()
        logger.info("prometheus instrumenting ended")
        return res

    def store_primitives(self, primitive_report):
        self.base_model.primitives.append(primitive_report)
        self.to_db()

    def get_primitive_byID(self, primitive_id):
        """
        Retrieve a primitive by its ID
        Args:

            primitive_id: the primitive ID

        Returns:
            The found primitive

        Raises:
            ValueError if the primitive is not found
        """
        primitive = next((item for item in self.base_model.primitives if item['result']['details']['id'] == primitive_id),
                         None)
        if primitive is None:
            raise ValueError('primitive {} not found'.format(primitive_id))
        return primitive

    def get_primitive_detailed_result(self, primitive_id=None, primitive=None):
        if primitive_id is not None:
            primitive = self.get_primitive_byID(primitive_id)
        return primitive['result']['details']['detailed-status']

    def rest_callback(self, requested_operation, session_id, status):
        """
        Perform a callback to the URL in the configuration.

        Args:

            requested_operation: The requested operation to be included in the callback

            session_id: The session ID to be included in the callback

            status: The status to be included in the callback

        Returns:
            The response from the callback
        """
        if "callback" in self.base_model.conf:
            logger.info("generating callback message")
            headers = {
                "Content-type": "application/json",
                "Accept": "application/json"
            }
            data = {
                "blueprint":
                    {
                        "id": self.get_id(),
                        "type": self.base_model.type
                    },
                "requested_operation": requested_operation,
                "session_id": session_id,
                "status": status
            }
            r = None
            try:
                r = requests.post(self.base_model.conf['callback'], json=data, params=None, verify=False, stream=True,
                                  headers=headers)
                return r
            except Exception as e:
                logger.error("ERROR - posting callback: ", e)
                return r
        else:
            logger.info("no callback message is needed")
            return None
