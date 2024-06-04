import json
import datetime
import requests
import traceback
import importlib
import abc
from nfvcl.models.blueprint.blueprint_base_model import BlueprintBaseModel, BlueNSD, BlueprintVersion
from nfvcl.models.blueprint.common import BluePrometheus
from nfvcl.models.blueprint.rest_blue import BlueGetDataModel, ShortBlueModel
from nfvcl.models.network import NetworkModel, PduModel
from nfvcl.nfvo import nsd_build_package, NbiUtil
from nfvcl.models.blueprint.blue_types import blueprint_types
from typing import List, Dict, Union, Callable
from fastapi import APIRouter, HTTPException, status
from nfvcl.topology.topology import Topology, build_topology
from nfvcl.utils.persistency import DB
from nfvcl.utils.log import create_logger


_db = DB()

# create logger
logger = create_logger('BASE_BLUEPRINT_BETA')


class BlueprintBaseBeta(abc.ABC):
    base_model: BlueprintBaseModel
    api_router: APIRouter
    api_day0_function: Callable
    api_day2_function: Callable

    @abc.abstractmethod
    def pre_initialization_checks(self) -> bool:
        """
        Checks if conditions are not respected for the blueprint life cycle (like having a k8s cluster).
        This method is called when processing a request, if a condition is not met, the request is dropped.
        Returns:
            true if conditions are satisfied.
        Raises:
            ValueError if some conditions are not met.
        """
        pass

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

    def __init__(self, conf: dict, id_: str, data: Union[Dict, None] = None, db: DB = None,
                 nbiutil: NbiUtil = None):
        if data:
            self.base_model = BlueprintBaseModel.model_validate(data)
        else:
            data = {}
            conf["blueprint_instance_id"] = id_
            blue_type = self.__class__.__name__
            data["type"] = blue_type
            data['conf'] = conf
            data['id'] = id_
            data['input_conf'] = conf
            self.base_model = BlueprintBaseModel.model_validate(data)

        self.base_model.version = BlueprintVersion.ver2_00
        self.topology_lock = None
        self.osm_nbiutil = nbiutil
        self.db = db

    @classmethod
    def from_db(cls, blue_id: str):
        logger.debug(f"Loading {blue_id} from DB")
        """
        Return a blueprint loaded from the database. If the blueprint type is not recognized, then an error is thrown.

        Args:
            blue_id: The ID of the blueprint in the database to be loaded.

        Returns:
            The loaded blueprint in its object form.
        """
        # Looks for the matching blueprint in the database
        db_data = _db.findone_DB("blueprint-instances", {'id': blue_id})
        if not db_data:
            raise ValueError('blueprint {} not found in DB or malformed'.format(blue_id))

        # Get the blueprint type
        type = db_data['conf']['type']
        if type not in blueprint_types:
            raise ValueError('type {} for blueprint {} not found'.format(type, blue_id))

        # Get the class
        blue_class = blueprint_types[type]
        try:
            # Call the constructor of the class using the db data as parameter
            return getattr(importlib.import_module("blueprints." + blue_class['module_name']),blue_class['class_name'])(db_data['conf'], blue_id, data=db_data)
        except Exception:
            logger.error(traceback.format_exc())
            raise ValueError('re-initialization for blueprint {} of type {} failed'.format(blue_id, db_data['type']))

    def delete_db(self):
        self.db.delete_DB("action_output", {'blue_id': self.base_model.id})
        self.db.delete_DB("blueprint-instances", {'id': self.base_model.id})

    def to_db(self):
        logger.debug(f"Saving {self.base_model.id} to DB")
        self.base_model.modified = datetime.datetime.now()
        # self.base_model.model_dump() is NOT working, some fields remain object
        data_serialized = json.loads(self.base_model.model_dump_json(by_alias=True))
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

            nsd_build_package(name, nsd.descr.model_dump(by_alias=True))
            res.append(name)
        return res

    def get_osm_ns_byname(self, name) -> Union[BlueNSD, None]:
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
        return self.base_model.model_dump()

    def print_short_summary(self) -> ShortBlueModel:
        return ShortBlueModel.model_validate(self.base_model.model_dump())

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
        logger.error(f"[ERROR] blueprint ns '{name}' not found")
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
            return ns.deploy_config.model_dump(by_alias=True)  # For compatibility with OSM nbi utils

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

    def get_topology(self) -> Topology:
        """
        Util to return the topology in the blueprints
        Returns:
            The topology of the NFVCL
        """
        topology = Topology.from_db(self.db, self.osm_nbiutil, self.topology_lock)
        return topology

    def topology_add_pdu(self, pdu: PduModel):
        """
        Add a PDU to the topology
        Args:
            pdu: The PDU to be added
        """
        topology = Topology.from_db(self.db, self.osm_nbiutil, self.topology_lock)
        topology.add_pdu(pdu)
        self.base_model.pdu.append(pdu.name)

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

    def topology_get_pdu_by_area(self, area_id: int) -> PduModel:
        """
        Retrieve the FIRST PDU from the topology by area

        Args:
            area_id: the area in witch the function is looking for the PDU
        """
        topology = Topology.from_db(self.db, self.osm_nbiutil, self.topology_lock)
        pdus: List[PduModel] = topology.get_pdus()
        return next((item for item in pdus if item.area == area_id), None)

    def topology_get_pdu_by_area_and_type(self, area_id: int, pdu_type: str) -> PduModel:
        """
        Retrieve the **FIRST** PDU from the topology by area and by type

        Args:
            area_id: the area in witch the function is looking for the PDU

            pdu_type: the type of the PDU
        """
        topology = Topology.from_db(self.db, self.osm_nbiutil, self.topology_lock)
        pdus: List[PduModel] = topology.get_pdus()
        pdu = next((item for item in pdus if item.area == area_id and item.type == pdu_type), None)
        return pdu

    def topology_del_network(self, net: NetworkModel, areas: List[int]):
        """
        Delete network from the topology and then remove it from every VIM of the area (terraform is set to true)

        Args:

            net: the network to be added in the topology

            areas: area ID list used to retrieve the VIM list. The network is removed from every VIM.
        """
        topology = Topology.from_db(self.db, self.osm_nbiutil, self.topology_lock)
        vims = []
        for area in areas:
            vims.append(topology.get_vim_name_from_area_id(area))

        topology.del_network(net, vims, terraform=True)

    def topology_get_network(self, network_name: str) -> NetworkModel:
        topology = Topology.from_db(self.db, self.osm_nbiutil, self.topology_lock)
        return topology.get_network(network_name)

    def get_vims(self):
        """
        For each area takes the FIRST VIM and add it to a list to be returned.

        Returns:
            A list of VIM, one for each deployment area.
        """
        deployment_areas = []
        # Cannot use model, the reason could be: Since every blueprint has its creation message, the message is
        # Different on blueprint basis. BUT in this case we suppose every blueprint has areas in is message.
        for area in self.base_model.conf['areas']:
            deployment_areas.append(area) if type(area) is int else deployment_areas.append(area['id'])

        vims_names = []
        vims = []
        topology = Topology.from_db(self.db, self.osm_nbiutil, self.topology_lock)
        for area in deployment_areas:
            area_vim = topology.get_vim_from_area_id_model(area)
            if area_vim.name not in vims_names:
                vims_names.append(area_vim.name)
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
        logger.info("Destroying the blueprint {}".format(self.get_id()))
        for p in self.base_model.pdu:
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
        res = [nsd for nsd in self.base_model.nsd_ if not (nsd.nsi_id == nsi)]
        self.base_model.nsd_ = res
        self.to_db()

    def set_timestamp(self, label: str, tstamp: datetime.datetime = None) -> datetime:
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

    def setup_prom_scraping(self, prom_info: BluePrometheus):
        """
        Set a scraping job on the requested prometheus server instance (present in the topology).
        The scraping job is configured on the node exporters that belong to the blueprint (present in
        self.base_model.node_exporters)
        Args:
            prom_info: info about prometheus instance, containing the prometheus instance ID (coherent with the one
            in the topology)

        Raises:
            ValueError if the prom server instance is not found in the topology.
        """
        if hasattr(prom_info, 'prom_server_id'):
            topology = Topology.from_db(self.db, self.osm_nbiutil, self.topology_lock)
            prom_server = topology.get_prometheus_server(prom_info.prom_server_id)
            # Add new jobs to the existing configuration
            prom_server.add_targets(targets=self.base_model.node_exporters)
            # Update the sd_file on the prometheus server.
            topology.update_prometheus_server(prom_server)
        else:
            raise ValueError("The prom_server_id is not present in the request")


    def disable_prom_scraping(self):
        """
        Remove all scraping jobs, for each target of the blueprint, on the prometheus server.

        Raises:
            ValueError if the prom server instance is not found in the topology.
        """
        topology = build_topology()
        if self.base_model.prometheus_scraper_id is None:
            e_msg = f"Impossible to disable prometheus scraping for blue {self.base_model.id}, no prometheus scraper is present"
            logger.error(e_msg)
        elif len(self.base_model.node_exporters)>0:
            prom_server = topology.get_prometheus_server(self.base_model.prometheus_scraper_id)
            prom_server.del_targets(self.base_model.node_exporters)
            topology.update_prometheus_server(prom_server)
            prom_server.update_remote_sd_file()
            logger.info(f"Successfully deleted all prometheus jobs for blue {self.base_model.id}")
        else:
            logger.info(f"There are NO prometheus jobs for blue {self.base_model.id}")

    def raise_http_error(self, error_msg: str, status_code: status):
        """
        Print the error in the console and raise HTTP error
        """
        logger.error(error_msg)
        raise HTTPException(status_code=status_code, detail=error_msg)
