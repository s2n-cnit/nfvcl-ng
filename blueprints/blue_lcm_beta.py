import json
import queue
import threading
import traceback
from logging import Logger
import redis
from typing import List

from models.event import Event
from utils import persistency
from .blueprint import BlueprintBase
from .blueprint_beta import BlueprintBaseBeta
from models.blueprint.rest_blue import ShortBlueModel, DetailedBlueModel
from models.blueprint.blue_events import BlueEventType
from nfvo import NbiUtil
from utils.log import create_logger
from utils.lcm_utils import day0_operation, day2_operation, checkVims, dayN_operation, destroy_blueprint
from utils.redis_utils.redis_manager import get_redis_instance, trigger_redis_event
from utils.redis_utils.topic_list import BLUEPRINT
from nfvo.osm_nbi_util import get_osm_nbi_utils

logger: Logger = create_logger('BLUELCMWORKER_BETA')


def get_blue_by_filter(blue_filter: dict, db: persistency.DB) -> List[dict]:
    return db.find_DB("blueprint-instances", blue_filter)


class LCMWorkersBeta:
    osmNbiUtil: NbiUtil
    db: persistency.DB
    redis_cli: redis.Redis

    def __init__(self, topology_lock):
        self.worker_queue = {}
        self.topology_lock = topology_lock
        self.osmNbiUtil = get_osm_nbi_utils()
        self.db = persistency.DB()
        self.redis_cli = get_redis_instance()

    def set_worker(self, blue: BlueprintBase) -> queue.Queue:
        self.worker_queue[blue.get_id()] = queue.Queue()
        blue.set_topology_lock(self.topology_lock)
        self.start_worker(blue)
        return self.worker_queue[blue.get_id()]

    def start_worker(self, blue: BlueprintBase):
        thread = threading.Thread(target=BlueLCMworkerBeta, name=blue.get_id(),
                                  args=(self.worker_queue[blue.get_id()], blue, [],))
        thread.daemon = True
        thread.start()

    @staticmethod
    def get_blue_detailed_summary(blue_filter: dict) -> List[DetailedBlueModel]:
        """
        Create and return a LIST of DetailedBlueModel (for all blueprints) that are used for showing blueprints data to
        the user.
        Args:
            blue_filter: a dictionary containing tha ID of the blueprint {'id': blue_id} to retrieve a specific
            blueprint.

        Returns:
            A list that contains the details for each blueprint.
        """
        db = persistency.DB()
        blues_mongo_cursor = get_blue_by_filter(blue_filter, db)
        blue_detailed_list: List[DetailedBlueModel] = []
        for blueprint in blues_mongo_cursor:
            detailed_blueprint = DetailedBlueModel.parse_obj(blueprint)
            detailed_blueprint.areas = blueprint['conf']['areas']
            blue_detailed_list.append(detailed_blueprint)
        return blue_detailed_list

    @staticmethod
    def get_blue_short_summary(blue_filter: dict) -> List[ShortBlueModel]:
        """
        Create and return a LIST of ShortBlueModel (for all blueprints) that are used to summarize blueprints data to
        the user.
        Args:
            blue_filter: a dictionary containing tha ID of the blueprint {'id': blue_id} to retrieve a specific
            blueprint.

        Returns:
            A list that contains a summary for each blueprint.
        """
        db = persistency.DB()
        blues_mongo_cursor = get_blue_by_filter(blue_filter, db)

        blue_undetailed_list: List[ShortBlueModel] = []
        # For each blueprint in the DB we create a summary
        for blueprint in blues_mongo_cursor:
            blueprint_short: ShortBlueModel = ShortBlueModel.parse_obj(blueprint)
            # We add summary data that need to be calculated
            blueprint_short.no_areas = len(blueprint['conf']['areas'])
            blueprint_short.no_nsd = len(blueprint['nsd_'])
            blueprint_short.no_primitives = len(blueprint['primitives'])

            blue_undetailed_list.append(blueprint_short)

        return blue_undetailed_list

    def get_worker(self, blue_id: str) -> queue.Queue:
        """
        Return the worker that handles requests for that blueprint. IF not present in the workers queue, the worker is
        initialized.

        Args:
            blue_id: The ID for witch the worked is searched.

        Returns:
            The worker of the blueprint
        """
        if self.worker_queue.get(blue_id):
            # check if the worker is running
            worker_names = [t.name for t in threading.enumerate()]
            if blue_id not in worker_names:
                logger.warning("Worker {} is not running, trying to reinitialize".format(blue_id))
                # recover the blue from the persistency
                # blue = unpickle_one_blue_by_id(blue_id)
                blue = BlueprintBaseBeta.from_db(blue_id)
                self.start_worker(blue)
            return self.worker_queue.get(blue_id)

        else:
            logger.warning("Worker queue {} is not available, trying to reinitialize".format(blue_id))
            # blue = unpickle_one_blue_by_id(blue_id)
            blue = BlueprintBaseBeta.from_db(blue_id)
            return self.set_worker(blue)

    def pop_worker(self, blue_id: str) -> queue.Queue:
        """
        Remove the worker of a blueprint from the queue (dict)
        Args:
            blue_id: the blueprint ID

        Returns:
            The removed element from the workers dictionary
        """
        # here we have to stop the thread
        return self.worker_queue.pop(blue_id, None)

    def destroy_worker(self, blue_id: str):
        """
        Destroy the worker of a blueprint (also destroy the blueprint itself)
        Args:
            blue_id: the ID of the worker (and the blueprint) to be destroyed
        """
        worker_queue = self.get_worker(blue_id)
        worker_queue.put({'requested_operation': 'stop'})
        self.pop_worker(blue_id)


class BlueLCMworkerBeta:
    osmNbiUtil: NbiUtil
    db: persistency.DB
    redis_cli: redis.Redis

    def __init__(self, session_queue: queue.Queue, blue: BlueprintBaseBeta, sessions: list = None, state: dict = None):
        # current_state = {session: str, day: str, stage: int, handler: str}
        self.osmNbiUtil = get_osm_nbi_utils()
        self.db = persistency.DB()
        self.redis_cli = get_redis_instance()
        self.blue = blue
        self.sessions = sessions
        self.state = state
        self.queue = session_queue
        self.blue.to_db()  # TODO is it necessary? Isn't that just loaded from the DB?

        while True:
            logger.info('worker {} awaiting for new job'.format(self.blue.get_id()))
            s_input = self.queue.get()

            logger.info('worker {} received new job {}'.format(self.blue.get_id(), s_input['requested_operation']))
            if s_input['requested_operation'] == 'stop':
                destroy_blueprint(self.osmNbiUtil, self.blue, self.db)
                logger.info('removing the worker thread of Blue {}'.format(self.blue.get_id()))
                break
            try:
                self.process_session(s_input['session_id'], s_input['msg'], s_input['requested_operation'])
            except Exception as e:
                logger.error(traceback.format_tb(e.__traceback__))
                logger.error(str(e))
                self.blue.base_model.status = 'error'
                self.blue.to_db()
            # if callback then send failure
            #    pass
            finally:
                self.queue.task_done()

        logger.info('worker thread of Blue {} destroyed'.format(self.blue.get_id()))

    def dump(self):
        return {'sessions': self.sessions, 'current_state': self.state}

    def abort_session(self, reply_msg: str, requested_operation: str, session_id: str):
        # self.blue.rest_callback(requested_operation, session_id, reply_msg, error=True)
        pass

    def process_session(self, session_id: str, msg: dict, requested_operation: str):
        logger.debug('updating blueprint {} with method {} session id {}'
                     .format(self.blue.get_id(), requested_operation, session_id))

        # Checking if requested operation is supported by the blueprint
        if requested_operation not in self.blue.get_supported_operations():
            self.abort_session('method {} not supported by the blueprint'
                               .format(requested_operation), requested_operation, session_id)

        # Check that all VIMs are onboarded on OSM
        checked_vims = checkVims(self.blue.get_vims(), self.osmNbiUtil)

        self.blue.base_model.status = 'processing'
        self.blue.base_model.current_operation = requested_operation
        self.blue.to_db()  # Updating the status to processing and requested operation
        self.trigger_event(BlueEventType.BLUE_START_PROCESSING, {})
        # for each session we might have multiple stages, each one composed by day0, day2, and dayN lists of handlers
        session_methods = self.blue.get_operation_methods(requested_operation)
        try:
            for stage in session_methods:
                logger.debug('current stage: {}'.format(json.dumps(stage)))
                if "day0" in stage:
                    self.blue.base_model.detailed_status = 'Day0/1'
                    self.blue.to_db()
                    self.trigger_event(BlueEventType.BLUE_START_DAY0, {})
                    for handler in stage['day0']:
                        if not day0_operation(handler, checked_vims, msg, self.osmNbiUtil, self.blue):
                            raise (AssertionError('error in Day0 operations'))
                        self.blue.to_db()
                    self.trigger_event(BlueEventType.BLUE_END_DAY0, self.blue.print_short_summary().dict())

                if "day2" in stage:
                    self.blue.base_model.detailed_status = 'Day2'
                    self.blue.to_db()
                    self.trigger_event(BlueEventType.BLUE_START_DAY2, {})
                    for handler in stage['day2']:
                        day2_operation(handler, msg, osmNbiUtil=self.osmNbiUtil, blue=self.blue, db=self.db)
                        self.blue.to_db()
                    self.trigger_event(BlueEventType.BLUE_END_DAY2, self.blue.print_short_summary().dict())

                if "dayN" in stage:
                    self.blue.base_model.detailed_status = 'DayN'
                    self.blue.to_db()
                    self.trigger_event(BlueEventType.BLUE_START_DAYN, {})
                    for handler in stage['dayN']:
                        dayN_operation(handler, msg, self.osmNbiUtil, self.blue)
                        self.blue.to_db()
                    self.trigger_event(BlueEventType.BLUE_END_DAYN, self.blue.print_short_summary().dict())

            self.blue.base_model.status = 'idle'
            self.blue.base_model.current_operation = ""
            self.blue.base_model.detailed_status = ""
            logger.info("Blue {} - session {} finalized".format(self.blue.get_id(), session_id))
            self.blue.to_db()
            self.trigger_event(BlueEventType.BLUE_END_PROCESSING, {})
            self.blue.rest_callback(requested_operation, session_id, "ready")

        except AssertionError as error:
            self.redis_cli.publish('blueprint', json.dumps(self.blue.print_short_summary()))
            self.blue.rest_callback(requested_operation, session_id, "failed")

    def trigger_event(self, event_type: BlueEventType, data: dict):
        event: Event = Event(operation=event_type, data=data)
        trigger_redis_event(redis_cli=self.redis_cli, topic=BLUEPRINT, event=event)
