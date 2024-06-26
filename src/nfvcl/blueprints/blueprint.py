import json
import datetime
import requests

from nfvcl.models.k8s.topology_k8s_model import K8sModel
from nfvcl.models.network import PduModel
from nfvcl.models.network.network_models import IPv4ReservedRange
from nfvcl.nfvo import nsd_build_package, NbiUtil
from .db_blue_model import DbBlue
from nfvcl.models.blueprint.blue_types import blueprint_types
from typing import List, Dict, Union, Callable
from fastapi import APIRouter
import traceback
import importlib
import abc
from nfvcl.topology.topology import Topology
from nfvcl.utils.persistency import DB
from nfvcl.utils.log import create_logger


_db = DB()
# create logger
logger = create_logger('BASE_BLUEPRINT')


class BlueprintBase(abc.ABC):
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

    def __init__(
            self,
            conf: dict,
            id_: str,
            data: Union[Dict, None] = None,
            db: DB = None,
            nbiutil: NbiUtil = None
    ):
        logger.warning("Blueprint v1 has been deprecated! Implement v2 instead!")
        if data:
            self.id = id_
            self.conf = data['conf']
            self.input_conf = data['input_conf']
            self.nsd_ = data['nsd_']
            # self.vnf_configurator = data['vnf_configurator']
            self.vnf_configurator = []
            self.primitives = data['primitives']
            self.action_to_check = data['action_to_check']
            self.timestamp = data['timestamp']
            self.config_len = data['config_len']
            self.created = data['created']
            self.status = data['status']
            self.detailed_status = data['detailed_status']
            self.current_operation = data['current_operation']
            self.modified = data['modified']
            self.supported_operations = data['supported_operations']
            self.blue_type = data['type']
            self.vnfd = data['vnfd'] if 'vnfd' in data else {}
            self.pdu = data['pdu'] if 'pdu' in data else []
            self.vnfi = data['vnfi'] if 'vnfi' in data else []
            self.deployment_units = data['deployment_units'] if 'deployment_units' in data else []
        else:
            self.id = id_
            self.conf = conf
            self.conf["blueprint_instance_id"] = id_
            self.input_conf = conf
            self.nsd_ = []
            self.vnfd = {}
            self.pdu = []
            self.vnf_configurator = []
            self.primitives = []
            self.action_to_check = []
            self.timestamp = {}
            self.config_len = {}
            self.created = datetime.datetime.now()
            self.status = 'idle'
            self.detailed_status = ""
            self.current_operation = ""
            self.modified = datetime.datetime.now()
            self.supported_operations = {}
            self.blue_type = self.__class__.__name__
            self.conf["blueprint_type"] = self.blue_type
            self.vnfi = []
            self.deployment_units = []
        self.topology_lock = None
        self.nbiutil = nbiutil
        self.db = db

    @classmethod
    def from_db(cls, blue_id):
        db_data = _db.findone_DB("blueprint-instances", {'id': blue_id})
        if not db_data:
            raise ValueError('blueprint {} not found in DB or malformed'.format(blue_id))
        data = DbBlue.model_validate(db_data).model_dump()
        if data['type'] not in blueprint_types:
            raise ValueError('type {} for blueprint {} not found'.format(data['type'], blue_id))
        blue_class = blueprint_types[data['type']]
        try:

            return getattr(importlib.import_module(
                "blueprints." + blue_class['module_name']), blue_class['class_name'])(data['conf'], blue_id, data=data)
        except Exception:
            logger.error(traceback.format_exc())
            raise ValueError('re-initialization for blueprint {} of type {} failed'
                             .format(blue_id, db_data['type']))

    def delete_db(self):
        self.db.delete_DB("action_output", {'blue_id': self.id})
        self.db.delete_DB("blueprint-instances", {'id': self.id})

    def to_db(self):
        self.modified = datetime.datetime.now()
        data = {'id': self.conf["blueprint_instance_id"], 'conf': self.conf, 'input_conf': self.input_conf,
                'nsd_': self.nsd_, 'vnf_configurator': self.vnf_configurator, 'primitives': self.primitives,
                'action_to_check': self.action_to_check, 'timestamp': self.timestamp, 'config_len': self.config_len,
                'created': self.created, 'status': self.status, 'detailed_status': self.detailed_status,
                'current_operation': self.current_operation, 'modified': self.modified,
                'supported_operations': self.supported_operations, 'type': self.blue_type, 'pdu': self.pdu,
                'vnfd': self.vnfd, 'deployment_units': self.deployment_units}
        data_serialized = json.loads(DbBlue.model_validate(data).json())
        if self.db.exists_DB("blueprint-instances", {'id': self.conf["blueprint_instance_id"]}):

            self.db.update_DB("blueprint-instances", data_serialized,
                              {'id': self.conf["blueprint_instance_id"]})
        else:

            self.db.insert_DB("blueprint-instances", data_serialized)

    def get_id(self) -> str:
        return self.conf["blueprint_instance_id"]

    def get_id_lower(self) -> str:
        """
        Return the lowercase id of the blueprint

        Returns:
            lowercase id of the blueprint
        """
        return str(self.conf["blueprint_instance_id"]).lower()

    def set_topology_lock(self, topo_lock) -> None:
        self.topology_lock = topo_lock

    def get_operation_methods(self, operation: str) -> List[Dict[str, List]]:
        return self.supported_operations.get(operation) if hasattr(self, "supported_operations") else []

    def get_supported_operations(self) -> List[str]:
        if hasattr(self, "supported_operations"):
            return list(self.supported_operations.keys())
        else:
            return []

    def build_packages(self, nsd_names) -> list:
        logger.info("Blue {} - Building " + str(len(self.nsd_)) + " nsd package".format(self.get_id()))
        res = []
        for n in self.nsd_:
            logger.debug(n['status'])
            if 'nsd:nsd-catalog' in n['descr']:
                name = n['descr']['nsd:nsd-catalog']['nsd'][0]['name']
            else:
                name = n['descr']['nsd']['nsd'][0]['name']

            if name not in nsd_names:
                continue

            if n['status'] != 'day0':
                logger.error("Blue {} -  the state of nsd {} is {}: aborting !"
                             .format(self.get_id(), name, n['status']))
                raise ValueError('NSD {} not in Day0 state'.format(name))

            nsd_build_package(name, n['descr'])
            res.append(name)
        return res

    def get_osm_ns_byname(self, name):
        for n in self.nsd_:
            if 'nsd' in n['descr']:
                n_descr = n['descr']['nsd']['nsd'][0]
            else:
                n_descr = n['descr']['nsd:nsd-catalog']['nsd'][0]
            if n_descr['name'] == name:
                return n
        return None

    def add_osm_nsd(self, name, ns_id):
        n_ = self.get_osm_ns_byname(name)
        if n_ is None:
            raise ValueError('Blueprint NSD not found')
        n_['nsd_id'] = ns_id
        return True

    def add_osm_nsi(self, name, ns_id):
        n_ = self.get_osm_ns_byname(name)
        if n_ is None:
            raise ValueError('Blueprint NSD not found')
        n_['nsi_id'] = ns_id
        return True

    def print_detailed_summary(self) -> dict:
        res = {}

        res.update({
            'id': self.get_id(),
            'type': self.conf["blueprint_type"],
            'created': self.created.strftime("%m/%d/%Y, %H:%M:%S") if hasattr(self, 'created') else None,
            'modified': self.modified.strftime("%m/%d/%Y, %H:%M:%S") if hasattr(self, 'modified') else None,
            'supported_ops': [key for key in self.supported_operations],
            'config': self.conf['config'],
            'areas': self.conf['areas'],
            'ns': [{
                'status': item['status'],
                'type': item['type'],
                'vim': item['vim'],
                'nsi_id': item['nsi_id'] if 'nsi_id' in item else None,
                'nsd_id': item['nsd_id'] if 'nsd_id' in item else None
            } for item in self.nsd_],
            'vnfd': self.vnfd if hasattr(self, 'vnfd') else [],
            'pdu': self.pdu if hasattr(self, 'pdu') else [],
            'primitives': []
        })

        _prims = self.primitives.copy()
        for p in _prims:
            p.update({'time': p['time'].strftime("%m/%d/%Y, %H:%M:%S")})
            logger.debug(p)
            res['primitives'].append(p)

        return res

    def print_short_summary(self) -> dict:
        return {
            'id': self.get_id(),
            'type': self.conf["blueprint_type"],
            'status': self.status if hasattr(self, 'status') else None,
            'detailed_status': self.detailed_status if hasattr(self, 'detailed_status') else None,
            'current_operation': self.current_operation if hasattr(self, 'detailed_status') else None,
            'created': self.created.strftime("%m/%d/%Y, %H:%M:%S") if hasattr(self, 'created') else None,
            'modified': self.modified.strftime("%m/%d/%Y, %H:%M:%S") if hasattr(self, 'modified') else None,
            'no_areas': len(self.conf["areas"]),
            'no_nsd': len(self.nsd_),
            'no_primitives': len(self.primitives)
        }

    def get_nsd(self) -> List:
        return self.nsd_

    def set_osm_status(self, name: str, status: str) -> bool:
        for n in self.nsd_:
            if 'nsd:nsd-catalog' in n['descr']:
                nsd_name = n['descr']['nsd:nsd-catalog']['nsd'][0]['name']
            else:
                nsd_name = n['descr']['nsd']['nsd'][0]['name']

            if nsd_name == name:
                n['status'] = status
                self.to_db()
                return True
        logger.error("[ERROR] blueprint ns not found")
        return False

    def deploy_config(self, nsd_id: str):
        ns = next((item for item in self.nsd_ if item['nsd_id'] == nsd_id), None)
        if ns is None:
            raise ValueError('NSD with id ' + nsd_id + ' not present in blueprint')
        if 'deploy_config' in ns:
            return ns['deploy_config']
        else:
            return None

    def get_vnf_data(self):
        # resetting the vnfi to rewrite
        self.vnfi = []
        self.deployment_units = []

        # getting all the vnf instances for the blueprint's network services
        nsi_ids = [item['nsi_id'] for item in self.nsd_]
        for nsi in nsi_ids:
            self.vnfi += self.nbiutil.get_vnfi_list(nsi)

        for vnf in self.vnfi:
            for du in vnf['vdur']:
                self.deployment_units.append({
                    'name': du['name'],
                    'vnfd-name': vnf['vnfd-ref'],
                    'ns_id': vnf['nsr-id-ref'],
                    'member-vnf-index-ref': vnf['member-vnf-index-ref'],
                    'ip-address': du['ip-address'],
                    'status': du['status'],
                    'type': 'vdu'
                })
        # FIXME: add kdus and pdus

    @abc.abstractmethod
    def get_ip(self):
        pass

    def topology_add_pdu(self, pdu: dict):
        topology = Topology.from_db(self.db, self.nbiutil, self.topology_lock)
        topology.add_pdu(PduModel.model_validate(pdu))
        self.pdu.append(pdu['name'])
        self.to_db()

    def topology_del_pdu(self, pdu_name: str):
        topology = Topology.from_db(self.db, self.nbiutil, self.topology_lock)
        topology.del_pdu(pdu_name)
        self.pdu = [item for item in self.pdu if item != pdu_name]
        self.to_db()

    def topology_get_pdu(self, pdu_name: str):
        topology = Topology.from_db(self.db, self.nbiutil, self.topology_lock)
        return topology.get_pdu(pdu_name).model_dump()

    def topology_get_pdu_by_area(self, area) -> dict:
        topology = Topology.from_db(self.db, self.nbiutil, self.topology_lock)
        pdus: List[PduModel] = topology.get_pdus()
        if type(area) is dict:
            return next((pdu.model_dump() for pdu in pdus if pdu.area == area['id']), None)
        else:
            return next((pdu.model_dump() for pdu in pdus if pdu.area == area), None)

    def topology_get_pdu_by_area_and_type(self, area_id: str, pdu_type: str) -> dict:
        topology = Topology.from_db(self.db, self.nbiutil, self.topology_lock)
        pdus: List[PduModel] = topology.get_pdus()
        return next((item.model_dump() for item in pdus if item.area == area_id and item.type == pdu_type), None)

    def topology_get_vim_by_area(self, area):
        topology = Topology.from_db(self.db, self.nbiutil, self.topology_lock)
        if type(area) is dict:
            return topology.get_vim_from_area_id(area['id'])
        else:
            return topology.get_vim_from_area_id(area)

    def topology_add_k8scluster(self, k8s_cluster_data: dict):
        topology = Topology.from_db(self.db, self.nbiutil, self.topology_lock)
        topology.add_k8scluster(K8sModel.model_validate(k8s_cluster_data))

    def topology_del_k8scluster(self):
        topology = Topology.from_db(self.db, self.nbiutil, self.topology_lock)
        topology.del_k8scluster(self.get_id())

    def topology_update_k8scluster(self, k8s_cluster: K8sModel):
        # Retrieving the topology
        topology = Topology.from_db(self.db, self.nbiutil, self.topology_lock)
        # Update the k8s cluster
        topology.update_k8scluster(k8s_cluster)

    def topology_add_network(self, net: dict, areas: list):
        topology = Topology.from_db(self.db, self.nbiutil, self.topology_lock)
        vim_names = set()
        for a in areas:
            if type(a) == int:
                vim_names.add(topology.get_vim_name_from_area_id(a))
                logger.debug("for area {} the following vims have been selected: {}".format(a, vim_names))
            else:
                vim_names.add(topology.get_vim_name_from_area_id(a['id']))
                logger.debug("for area {} the following vims have been selected: {}".format(a['id'], vim_names))
        topology.add_network(net, list(vim_names), terraform=True)

    def topology_del_network(self, net: dict, areas: Union[List[int], List[dict]]):
        topology = Topology.from_db(self.db, self.nbiutil, self.topology_lock)
        vims = set()
        for a in areas:
            if type(a) == int:
                vims.add(topology.get_vim_name_from_area_id(a))
                logger.debug("Blue {} - for area {} the following vims have been selected: {}"
                             .format(self.get_id(), a, vims))
            elif type(a) == dict:
                vims.add(topology.get_vim_name_from_area_id(a['id']))
                logger.debug("Blue {} - for area {} the following vims have been selected: {}"
                             .format(self.get_id(), a['id'], vims))
            else:
                raise ValueError("Type error in areas")
        topology.del_network(net, list(vims), terraform=True)

    def topology_get_network(self, network_name: str) -> dict:
        topology = Topology.from_db(self.db, self.nbiutil, self.topology_lock)
        return topology.get_network(network_name).model_dump()

    def topology_reserve_ip_range(self, lb_pool: dict, range_length: int) -> IPv4ReservedRange:
        topology = Topology.from_db(self.db, self.nbiutil, self.topology_lock)
        reserved_range: IPv4ReservedRange = topology.reserve_range(lb_pool['net_name'], range_length, self.get_id())
        return reserved_range

    def topology_release_ip_range(self):
        topology = Topology.from_db(self.db, self.nbiutil, self.topology_lock)
        return topology.release_ranges(owner=self.get_id())

    def get_vim_name(self, area: Union[int, dict]) -> str:
        topology = Topology.from_db(self.db, self.nbiutil, self.topology_lock)
        if type(area) == int:
            return topology.get_vim_name_from_area_id(area)
        else:
            return topology.get_vim_name_from_area_id(area['id'])

    def get_vim(self, area: Union[int, dict]) -> dict:
        topology = Topology.from_db(self.db, self.nbiutil, self.topology_lock)
        if type(area) == int:
            return topology.get_vim_from_area_id(area)
        else:
            return topology.get_vim_from_area_id(area['id'])

    def get_vims(self):
        """
        For each area, it returns the FIRST VIM of the area.

        Returns:
            a list of VIMs, at most, one per area
        """
        deployment_areas = set()
        for area in self.conf['areas']:
            deployment_areas.add(area) if type(area) is int else deployment_areas.add(area['id'])

        vims_names = set()
        vims = []
        topology = Topology.from_db(self.db, self.nbiutil, self.topology_lock)
        for area in deployment_areas:
            area_vim = topology.get_vim_from_area_id(area)
            if area_vim['name'] not in vims_names:
                vims_names.add(area_vim['name'])
                vims.append(area_vim)
        logger.debug('*************************************\n{}*************************************\n'.format(vims))
        return vims

    def destroy(self):
        logger.info("Destroying")
        if hasattr(self, "pdu"):
            for p in self.pdu:
                logger.debug("deleting pdu {}".format(p))
                self.topology_del_pdu(p)
        self._destroy()
        self.delete_db()

    @abc.abstractmethod
    def _destroy(self):
        pass

    def delete_nsd(self, nsi: str):
        res = [i for i in self.nsd_ if 'nsi_id' in i and not (i['nsi_id'] == nsi)]
        self.nsd_ = res
        self.to_db()

    def get_timestamp(self, label: str, tstamp: datetime.datetime = None) -> None:
        self.timestamp[label] = tstamp if tstamp else datetime.datetime.now()

    def get_performance(self):
        result = {'blueprint_id': self.get_id(), 'blueprint_type': self.blue_type,
                  'start_time': self.timestamp['day0_start'].strftime("%H:%M:%S.%f"), 'measures': []}
        for key, value in self.timestamp.items():
            # HERE config len - check label
            if key != 'day0_start':
                delta = value - self.timestamp['day0_start']
                result['measures'].append({'label': key, 'duration': int(delta.total_seconds() * 1000), 'unit': 'ms'})
        for key, value in self.config_len.items():
            for r in result['measures']:
                if r['label'] == key:
                    r['config_len'] = value

        return result

    def get_configlen(self, label, config):
        self.config_len[label] = len(json.dumps(config))

    """    def findNsdTemplate(self, category_, type_, flavors_):
        templates = db.find_DB(
            "nsd_templates", {'category': category_, 'type': type_})
        n_ = next((item for item in templates if (set(flavors_['include']) <= set(
            item['flavors'])) and not bool(set(flavors_['exclude']) & set(item['flavors']))), None)
        if n_ is None:
            raise ValueError('NSD template not found in the catalogue')
        return n_['descriptor']
"""

    @staticmethod
    def updateVnfdNames(vnfd_names, nsd_):
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
            for c in self.vnf_configurator:
                if c.blue_type() == args["vnf_type"]:
                    res.append(c.enable_elk(args)[-1])
            return res
        elif "ns_type" in args:
            for s in self.nsd_:
                if s["type"] == args["ns_type"]:
                    for c in self.vnf_configurator:
                        if c.nsd_id == s.nsd_id:
                            res.append(c.enable_elk(args)[-1])
            return res
        elif "nsi_id" in args:
            for s in self.nsd_:
                if s["nsi_id"] == args["nsi_id"]:
                    for c in self.vnf_configurator:
                        if c.nsd_id == s.nsd_id:
                            res.append(c.enable_elk(args)[-1])
            return res
        elif "nsd_id" in args:
            for s in self.nsd_:
                if s["nsd_id"] == args["nsd_id"]:
                    for c in self.vnf_configurator:
                        if c.nsd_id == s.nsd_id:
                            if "vnfd_id" in args:
                                if c.nsd['member-vnfd-id'] == args["vnfd_id"]:
                                    res.append(c.enable_elk(args)[-1])
                            else:
                                res.append(c.enable_elk(args)[-1])
        else:
            for c in self.vnf_configurator:
                res.append(c.enable_elk(args)[-1])

        return res

    def store_primitives(self, primitive_report):
        self.primitives.append(primitive_report)
        self.to_db()

    def get_primitive_byID(self, primitive_id):
        primitive = next((item for item in self.primitives if item['result']['details']['id'] == primitive_id), None)
        if primitive is None:
            raise ValueError('primitive {} not found'.format(primitive_id))
        return primitive

    def get_primitive_detailed_result(self, primitive_id=None, primitive=None):
        if primitive_id is not None:
            primitive = self.get_primitive_byID(primitive_id)
        return primitive['result']['details']['detailed-status']

    def rest_callback(self, requested_operation, session_id, status):
        if "callback" in self.conf and self.conf["callback"] and self.conf["callback"] != "":
            logger.info("generating callback message")
            headers = {
                "Content-type": "application/json",
                "Accept": "application/json"
            }
            data = {
                "blueprint":
                    {
                        "id": self.get_id(),
                        "type": self.blue_type
                    },
                "requested_operation": requested_operation,
                "session_id": session_id,
                "status": status
            }
            r = None
            try:
                r = requests.post(self.conf['callback'], json=data, params=None, verify=False, stream=True,
                                  headers=headers)
                return r
            except Exception as e:
                logger.error("ERROR - posting callback: ", e)
                return r
        else:
            logger.info("no callback message is needed")
            return None
