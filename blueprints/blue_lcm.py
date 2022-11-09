import datetime
import json
import queue
import threading
import time
import subprocess
import traceback
import redis
from typing import List
from utils import persistency
from .blueprint import BlueprintBase
from .rest_blue import ShortBlueModel, DetailedBlueModel
from nfvo import NbiUtil, get_nsd_name
from utils.util import *

logger = create_logger('BlueLCMWorker')
nbiUtil = NbiUtil(username=osm_user, password=osm_passwd, project=osm_proj, osm_ip=osm_ip, osm_port=osm_port)
db = persistency.DB()
redis_cli = redis.Redis(host=redis_host, port=redis_port, decode_responses=True, encoding="utf-8")

def get_blue_by_filter(blue_filter: dict) -> List[dict]:
    return db.find_DB("blueprint-instances", blue_filter)


class LCMWorkers:
    def __init__(self, topology_lock):
        self.worker_queue = {}
        self.topology_lock = topology_lock

    def set_worker(self, blue: BlueprintBase) -> queue.Queue:
        self.worker_queue[blue.get_id()] = queue.Queue()
        blue.set_topology_lock(self.topology_lock)
        self.start_worker(blue)
        return self.worker_queue[blue.get_id()]

    def start_worker(self, blue: BlueprintBase):
        thread = threading.Thread(target=BlueLCMworker, name=blue.get_id(),
                                  args=(self.worker_queue[blue.get_id()], blue, [], ))
        thread.daemon = True
        thread.start()

    @staticmethod
    def get_blue_detailed_summary(blue_filter: dict) -> List[DetailedBlueModel]:
        blues = get_blue_by_filter(blue_filter)
        # logger.debug(blues)
        # return [item.print_detailed_summary() for item in blues]
        return [DetailedBlueModel.parse_obj(item) for item in blues]

    @staticmethod
    def get_blue_short_summary(blue_filter: dict) -> List[ShortBlueModel]:
        blues = get_blue_by_filter(blue_filter)

        return [ShortBlueModel.parse_obj(
            {
                'id': item['id'],
                'type': item['type'],
                'status': item['status'],
                'detailed_status': item['detailed_status'],
                'current_operation': item['current_operation'],
                'created': item['created'],
                'modified': item['modified'],
                'no_areas': len(item['conf']['areas']),
                'no_nsd': len(item['nsd_']),
                'no_primitives': len(item['primitives']),
            }
        ) for item in blues]

    def get_worker(self, blue_id: str) -> queue.Queue:
        if self.worker_queue.get(blue_id):
            # check if the worker is running
            worker_names = [t.name for t in threading.enumerate()]
            if blue_id not in worker_names:
                logger.warning("worker {} not running, trying to reinitialize".format(blue_id))
                # recover the blue from the persistency
                # blue = unpickle_one_blue_by_id(blue_id)
                blue = BlueprintBase.from_db(blue_id)
                self.start_worker(blue)
            return self.worker_queue.get(blue_id)

        else:
            logger.warning("worker queue {} not available, trying to reinitialize".format(blue_id))
            # blue = unpickle_one_blue_by_id(blue_id)
            blue = BlueprintBase.from_db(blue_id)
            return self.set_worker(blue)

    def pop_worker(self, blue_id: str) -> queue.Queue:
        # here we have to stop the thread
        return self.worker_queue.pop(blue_id, None)

    def destroy_worker(self, blue_id: str):
        worker_queue = self.get_worker(blue_id)
        worker_queue.put({'requested_operation': 'stop'})
        self.pop_worker(blue_id)


class BlueLCMworker:
    def __init__(self, session_queue: queue.Queue, blue: BlueprintBase, sessions: list = None, state: dict = None):
        # current_state = {session: str, day: str, stage: int, handler: str}
        self.blue = blue
        self.sessions = sessions
        self.state = state
        self.queue = session_queue
        self.update_db()

        while True:
            logger.info('worker {} awaiting for new job'.format(self.blue.get_id()))
            s_input = self.queue.get()

            logger.info('worker {} received new job {}'.format(self.blue.get_id(), s_input['requested_operation']))
            if s_input['requested_operation'] == 'stop':
                self.destroy()
                logger.info('removing the worker thread of Blue {}'.format(self.blue.get_id()))
                break
            try:
                self.process_session(s_input['session_id'], s_input['msg'], s_input['requested_operation'])
            except Exception as e:
                logger.error(traceback.format_tb(e.__traceback__))
                logger.error(str(e))
                self.blue.status = 'error'
                self.update_db()
            # if callback then send failure
            #    pass
            finally:
                self.queue.task_done()

        logger.info('worker thread of Blue {} destroyed'.format(self.blue.get_id()))

    def update_db(self) -> None:
        self.blue.to_db()

    def destroy(self):
        self.blue.status = 'processing'
        self.blue.current_operation = 'Destroy'
        self.blue.detailed_status = 'removing Network Service instances'
        self.update_db()
        nsi_list = []
        for nsd in self.blue.get_nsd():
            if 'nsd_id' not in nsd:
                logger.warning("Blue {} - no nsd id for this nsd ... skipping!".format(self.blue.get_id()))
                continue

            if 'nsi_id' in nsd:
                logger.info("Blue {} - deleting nsi= {}".format(self.blue.get_id(), nsd['nsi_id']))
                nsi_list.append(nsd['nsi_id'])
            else:
                logger.warning("Blue {} - no nsi id for nsd {}... skipping!".format(self.blue.get_id(), nsd['nsd_id']))

        self.init_dayN(nsi_list)
        self.blue.detailed_status = 'destroying blueprint and temporary files'
        self.update_db()
        logger.info("Blue {} - destroying blueprint".format(self.blue.get_id(), ))

        logger.debug("Blue {} - removing temporary day2 files".format(self.blue.get_id(), ))
        subprocess.run(['rm', '-rf', 'day2_files/_{}*'.format(self.blue.get_id())])
        subprocess.run(['rm', '-rf', 'vnf_packages/{}_*'.format(self.blue.get_id())])
        subprocess.run(['rm', '-rf', '/tmp/nsd_packages/*_{}*'.format(self.blue.get_id())])

        db.delete_DB("action_output", {'blue_id': self.blue.get_id()})
        self.blue.delete_db()
        self.blue.destroy()

    def dump(self):
        return {'sessions': self.sessions, 'current_state': self.state}

    def abort_session(self, reply_msg: str, requested_operation: str, session_id: str):
        # self.blue.rest_callback(requested_operation, session_id, reply_msg, error=True)
        pass

    def process_session(self, session_id: str, msg: dict, requested_operation: str):
        # day0_start = datetime.datetime.now()
        logger.debug('updating blueprint {} with method {} session id {}'
                     .format(self.blue.get_id(), requested_operation, session_id))

        # check if requested operation is supported by the blueprint
        if requested_operation not in self.blue.get_supported_operations():
            self.abort_session('method {} not supported by the blueprint'
                               .format(requested_operation), requested_operation, session_id)

        checked_vims = self.checkVims(self.blue.get_vims())

        self.blue.status = 'processing'
        self.blue.current_operation = requested_operation
        self.update_db()
        redis_cli.publish('blueprint', json.dumps(self.blue.print_short_summary()))
        # for each session we might have multiple stages, each one composed by day0, day2, and dayN lists of handlers
        session_methods = self.blue.get_operation_methods(requested_operation)
        # logger.info(session_methods)
        try:
            for stage in session_methods:
                logger.debug('current stage: {}'.format(json.dumps(stage)))
                if "day0" in stage:
                    self.blue.detailed_status = 'Day0/1'
                    self.update_db()
                    redis_cli.publish('blueprint', json.dumps(self.blue.print_short_summary()))
                    for handler in stage['day0']:
                        if not self.day0_operation(handler, checked_vims, msg):
                            raise (AssertionError('error in Day0 operations'))
                        self.update_db()
                        redis_cli.publish('blueprint', json.dumps(self.blue.print_short_summary()))

                if "day2" in stage:
                    self.blue.detailed_status = 'Day2'
                    self.update_db()
                    redis_cli.publish('blueprint', json.dumps(self.blue.print_short_summary()))
                    for handler in stage['day2']:
                        self.day2_operation(handler, msg)
                        self.update_db()
                        redis_cli.publish('blueprint', json.dumps(self.blue.print_short_summary()))

                if "dayN" in stage:
                    self.blue.detailed_status = 'DayN'
                    self.update_db()
                    redis_cli.publish('blueprint', json.dumps(self.blue.print_short_summary()))
                    for handler in stage['dayN']:
                        self.dayN_operation(handler, msg)
                        self.update_db()
                        redis_cli.publish('blueprint', json.dumps(self.blue.print_short_summary()))

            self.blue.status = 'idle'
            self.blue.current_operation = None
            self.blue.detailed_status = None
            logger.info("Blue {} - session {} finalized".format(self.blue.get_id(), session_id))
            self.update_db()
            redis_cli.publish('blueprint', json.dumps(self.blue.print_short_summary()))
            self.blue.rest_callback(requested_operation, session_id, "ready")

        except AssertionError as error:
            redis_cli.publish('blueprint', json.dumps(self.blue.print_short_summary()))
            self.blue.rest_callback(requested_operation, session_id, "failed")
            self.abort_session(str(error), requested_operation, session_id)

    def day0_operation(self, handler, checked_vims: list, msg: dict):
        logger.info("Blue {} - starting Day 0 operations".format(self.blue.get_id()))
        # run the method to create blue's NSDs
        nsd_names = getattr(self.blue, handler['method'])(msg)
        # instantiate nsd
        if self.instantiate_blueprint(checked_vims, nsd_names) is False:
            return False
        self.update_db()
        # wait for NSDs becoming ready
        if self.wait_for_blue_day1(nsd_names) is False:
            return False
        self.update_db()
        # get IP addresses of VNFs
        self.blue.get_ip()
        # save blue binary dump
        return True

    def day2_operation(self, handler, msg: dict):
        logger.info("Blue {} - starting Day 2 operations".format(self.blue.get_id()))
        if handler.get('callback') is not None:
            self.init_day2(getattr(self.blue, handler['method'])(msg),
                           blue_callback=getattr(self.blue, handler['callback']))
        else:
            self.init_day2(getattr(self.blue, handler['method'])(msg))
        self.update_db()

    def dayN_operation(self, handler, msg: dict):
        logger.info("Blue {} - starting dayN operations".format(self.blue.get_id()))
        self.init_dayN(getattr(self.blue, handler['method'])(msg))

    @staticmethod
    def checkVims(vims):
        vim_list = list()

        for vim in vims:
            vim_object = nbiUtil.get_vim_by_tenant_and_name(vim['name'], vim['vim_tenant_name'])
            if vim_object is None:
                raise AssertionError('VIM {} not onboarded in the NFVO'.format(vim['name']))
            vim_list.append(vim_object)

        return vim_list

    def instantiate_blueprint(self, vims: list, nsd_names: list):

        self.blue.get_timestamp('day0_buildpackages_start')
        logger.debug('Blue {} - Day0 - building NSD packages'.format(self.blue.get_id()))

        # Day0 handlers must return the names of nsd to be instantiated
        self.blue.build_packages(nsd_names=nsd_names)

        self.blue.get_timestamp('day0_onboarding_start')
        nsd_list = []

        for nsd_name in nsd_names:
            # NOTE: we could support here OSM catalogues

            r = nbiUtil.nsd_reonboard(nsd_name)

            if r['error']:
                logger.error("Blue {} - Day0 onboarding nsd {} failed, reason: {}"
                             .format(self.blue.get_id(), nsd_name, json.dumps(r['data'])))
                self.blue.set_osm_status(nsd_name, 'error')
                raise AssertionError("Blue {}: Day0 onboarding nsd {} failed, reason: {}"
                                     .format(self.blue.get_id(), nsd_name, json.dumps(r['data'])))
                # return False

            # addinng nsd id to the Blue
            self.blue.add_osm_nsd(nsd_name, r['data']['id'])
            self.blue.set_osm_status(nsd_name, 'onboarded')

            nsd_list.append({'nsd_id': r['data']['id'], 'name': nsd_name})

        self.blue.get_timestamp("day0_end")

        # Day1 starts from here
        for nsd_item in [item for item in self.blue.get_nsd() if item['descr']['nsd']['nsd'][0]['name'] in nsd_names]:
            logger.info("Blue {} - Day1 - instantiating NSD={} on VIM {}"
                        .format(self.blue.get_id(), nsd_item['descr']['nsd']['nsd'][0]['name'], nsd_item['vim']))

            nsd_name = nsd_item['descr']['nsd']['nsd'][0]['name']
            vim_ = next(v_ for v_ in vims if v_['name'] == nsd_item['vim'])
            r = nbiUtil.instantiate_ns(
                nsd_item['nsd_id'],
                nsd_name,
                "automatically generated by CNIT S2N NFVCL",
                vim_['_id'],
                self.blue.deploy_config(nsd_item['nsd_id'])
            )
            if r['error']:
                logger.error("Blue {}: Day1 nsd {} instantiation failed, reason: {}"
                             .format(self.blue.get_id(), nsd_name, json.dumps(r['data'])))
                self.blue.set_osm_status(nsd_name, 'error')
                return False

            self.blue.add_osm_nsi(nsd_name, r['data']['id'])
            self.blue.set_osm_status(nsd_name, 'day1')
        return True

    def wait_for_blue_day1(self, ns_to_check: list):
        self.blue.get_timestamp('day1_osm')

        logger.debug("Blue {} - wait_for_blue_day1(): number of NSI to check: {}"
                     .format(self.blue.get_id(), str(len(ns_to_check))))

        nsi_list = []
        for ns_item in self.blue.get_nsd():
            if get_nsd_name(ns_item['descr']) in ns_to_check:
                nsi_list.append(ns_item['nsi_id'])

        # NFVCL callbacks are not working in OSM -- commented code for future usage

        # callback_url = 'http://{}:{}/nfvcl/callback'.format(nfvcl_ip, str(nfvcl_port))
        # subscribe to osm
        # for nsi in nsi_list:
        #    if not nbiUtil.subscribe_ns_notifications(nsi, callback_url):
        #        logger.error("Blue {} - not possible to subscribe to events of service {}"
        #                     .format(self.blue.get_id(), nsi, callback_url))
        #        return False

        while len(ns_to_check) > 0:
            time.sleep(5)
            for ns_item in self.blue.get_nsd():
                nsd_name = get_nsd_name(ns_item['descr'])
                if nsd_name in ns_to_check:
                    try:
                        r = nbiUtil.check_ns_instance(ns_item['nsi_id'])
                    except ValueError as value_exception:
                        logger.error('ValueError received')
                        logger.error(value_exception)
                        if len(value_exception.args) > 0 and \
                                "Deploying at VIM: b\'\'" in value_exception.args[0]:
                            logger.warning("Blue {} - NSI {} failed during day1 operations. Trying to recover."
                                           .format(self.blue.get_id(), ns_item['nsi_id']))
                            nbiUtil.ns_delete(ns_item['nsi_id'], True)
                            nsd_name = ns_item['descr']['nsd']['nsd'][0]['name']
                            r = nbiUtil.instantiate_ns(
                                ns_item['nsd_id'],
                                nsd_name,
                                "automatically generated by CNIT S2N NFVCL",
                                ns_item['deploy_config']['vimAccountId'],
                                self.blue.deploy_config(ns_item['nsd_id'])
                            )
                            if r['error']:
                                logger.error("Blue {} - Day1 nsd {} instantiation failed, reason: {}"
                                             .format(self.blue.get_id(), nsd_name, json.dumps(r['data'])))
                                raise ValueError('Healing operation on NS not successful')
                            self.blue.add_osm_nsi(nsd_name, r['data']['id'])
                            logger.warn('Blue {} - the new nsi_id is {}'.format(self.blue.get_id(), r['data']['id']))
                            self.blue.set_osm_status(nsd_name, 'day1')
                            # restart day 1 waiting loop
                            return self.wait_for_blue_day1(ns_to_check)
                        else:
                            logger.warn('Exception not handled for self-healing')
                            raise value_exception

                    logger.info("Blue {} - nsi: {} status: {}"
                                .format(self.blue.get_id(), ns_item['nsi_id'], r["config-status"]))
                    if r["config-status"] == 'configured':
                        ns_to_check.remove(nsd_name)
                        self.blue.set_osm_status(nsd_name, 'day2')
                        self.blue.get_timestamp('day1_end:' + nsd_name)
                    if "error" in r["config-status"] or "blocked" in r["config-status"] or \
                            "failed" in r["config-status"] or "failed" in r['operational-status']:
                        ns_to_check.remove(nsd_name)
                        self.blue.set_osm_status(nsd_name, r["config-status"])
                        return False
        logger.info("Blue {} - instantiation completed".format(self.blue.get_id()))
        self.blue.get_timestamp('day1_end')
        return True

    def init_day2(self, day2_primitives, blue_callback=None):
        self.blue.get_timestamp('day2_start')

        error_day2 = False
        results = []

        for p in day2_primitives:
            self.blue.get_timestamp("Blue {} - Day 2 start - NSD {} primitive for VNFD {}".format(
                    self.blue.get_id(),
                    p['ns-name'],
                    str(p['primitive_data']['member_vnf_index'])
                )
            )
            logger.debug(p)

            osm_ns = self.blue.get_osm_ns_byname(p['ns-name'])
            logger.debug(osm_ns)

            nsi_id = osm_ns['nsi_id'] if 'nsi_id' not in p else p['nsi_id']
            
            r = nbiUtil.execute_primitive(nsi_id, p['primitive_data'])

            results.append({"result": r, "primitive": p, "time": datetime.datetime.now()})
            self.blue.store_primitives(results[-1])

            self.blue.get_timestamp("Blue {} - Day 2 stop - NSD {} primitive for VNFD {}".format(
                self.blue.get_id(), p['ns-name'], str(p['primitive_data']['member_vnf_index'])))
            self.blue.get_configlen("Blue {} - Day 2 start - NSD {} primitive for VNFD {}".format(
                self.blue.get_id(), p['ns-name'], str(p['primitive_data']['member_vnf_index'])),
                p['primitive_data']['primitive_params'])

            if "completed" in r['charm_status']:
                self.blue.set_osm_status(p['ns-name'], 'day2')
                logger.info("Blue {} - {} correctly configured".format(self.blue.get_id(), p['ns-name']))
            else:
                error_day2 = True
                self.blue.set_osm_status(p['ns-name'], 'day2 error')
                logger.error("Blue {} - Day 2 - nsd {} failed in Day2 operations: {}"
                             .format(self.blue.get_id(), p['ns-name'], json.dumps(r)))

        if error_day2:
            logger.error("Blue {} - Day 2 - Error applying Day2 operations".format(self.blue.get_id()))
            return False

        # Day2 callback for the Blueprint object
        if blue_callback is not None:
            logger.info("Blue {} - Performing Day 2 callback".format(self.blue.get_id()))
            blue_callback(results)

        self.blue.get_timestamp('Blue {} - Day 2 end'.format(self.blue.get_id()))
        db.insert_DB("nfv_performance", self.blue.get_performance())
        return True

    def init_dayN(self, nsi_list):
        if nsi_list is None:
            logger.info("Blue {}: DayN - no day N operations to be performed".format(self.blue.get_id()))
            return True

        nsd_to_delete = []
        vnfd_to_delete = []

        # get nsd and vnfd
        for nsi in nsi_list:
            nsd_conf = next((item for item in self.blue.nsd_ if item.get('nsi_id') == nsi), None)
            if nsd_conf is None:
                logger.warn('nsi {} non found in blue {}, continuing...'.format(nsi, self.blue.get_id()))
                continue
            if 'nsd_id' in nsd_conf:
                nsd_to_delete.append(nsd_conf['nsd_id'])
            for v in nsd_conf['descr']['nsd']['nsd'][0]['vnfd-id']:
                vnfd_to_delete.append(v)

        for nsi in nsi_list:
            logger.debug("Blue {} - DayN - terminating nsi {}".format(self.blue.get_id(), nsi))
            r = nbiUtil.ns_delete(nsi)
            logger.debug("Blue {} - DayN - nsi {} termination result: {}".format(self.blue.get_id(), nsi, json.dumps(r)))

        nsi_to_check = nsi_list[:]  # copy not by reference
        while len(nsi_to_check) > 0:
            vnfo_nsi_list = nbiUtil.get_nsi_list()
            if vnfo_nsi_list is None:
                logger.warn("Blue {} - nsi list not found in the NFVO. Skipping...".format(self.blue.get_id()))
                break

            for n_index, n_value in enumerate(nsi_to_check):
                nsi = next((item for item in vnfo_nsi_list if item['id'] == n_value), None)
                if nsi is None:
                    logger.debug('Blue {} - NS instance {} deleted'.format(self.blue.get_id(), n_value))
                    nsi_to_check.pop(n_index)

        for nsd in nsd_to_delete:
            logger.debug("Blue {} - DayN - deleting nsd {}".format(self.blue.get_id(), nsd))
            r = nbiUtil.nsd_delete(nsd)
            logger.debug("Blue {} - DayN - nsd {} deletion result: {}".format(self.blue.get_id(), nsd, json.dumps(r)))

        nfvo_vnfd_list = nbiUtil.get_vnfd_list()
        logger.info("Blue {}: VNFD to be deleted: {}".format(self.blue.get_id(), vnfd_to_delete))
        for vnfd in vnfd_to_delete:
            nfvo_vnfd = next((item for item in nfvo_vnfd_list if item['id'] == vnfd), None)
            if nfvo_vnfd is None:
                continue
            logger.debug("Blue {} - DayN - deleting vnfd {} {}".format(self.blue.get_id(), nfvo_vnfd['id'],
                                                                      nfvo_vnfd['_id']))
            r = nbiUtil.delete_vnfd(nfvo_vnfd['_id'])
            logger.debug("Blue {} - DayN - vnfd {} {} deletion result:".format(self.blue.get_id(), nfvo_vnfd['id'],
                                                                              nfvo_vnfd['_id'], json.dumps(r)))

        for nsi in nsi_list:
            self.blue.delete_nsd(nsi)
