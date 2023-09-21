from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Union
from utils.log import create_logger
from utils.persistency import DB

db = DB()


class AnsiblePlaybookResult(BaseModel):
    playbook: str
    stdout: dict
    stderr: str


class ActionResultModel(BaseModel):
    result: List[AnsiblePlaybookResult]
    action_id: str
    nsd_id: str
    vnfd_id: Union[str, int]
    blue_id: str


day2_router = APIRouter(
    prefix="/nfvcl_day2",
    tags=["Day2 VNF Manager callbacks"],
    responses={404: {"description": "Not found"}},
)

logger = create_logger('Day2 Action')


@day2_router.post("/actions", status_code=200)
def post(msg: ActionResultModel):
    # logger.debug('**** action output received ***')
    # logger.info(msg)
    logger.info('action output received for blue {}, action id: {}'.format(msg.blue_id, msg.action_id))
    # we have an action_id... we could include all these actions output into a mongo collection, and
    # indexing them by action_id. Later the running blueprint could look for each of them in the db.

    # NOTE: MongoDB cannot accept docs with '.' in the keys, therefore we dump 'results' as json string
    action_item = {
        "result": [],
        "action_id": msg.action_id,
        "nsd_id": msg.nsd_id,
        "vnfd_id": msg.vnfd_id,
        "blue_id": msg.blue_id
    }
    for item in msg.result:
        action_item["result"].append(
            {
                'playbook': item.playbook,
                'stdout': item.stdout,
                'stderr': item.stderr
            }
        )
    db.insert_DB("action_output", action_item)



