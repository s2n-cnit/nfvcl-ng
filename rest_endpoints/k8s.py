from fastapi import APIRouter, HTTPException
from rest_endpoints.nfvcl_callback import callback_router
import pickle
import traceback
from main import *


k8s_router = APIRouter(
    prefix="/k8s",
    tags=["Kubernetes cluster onboarding"],
    responses={404: {"description": "Not found"}},
)
logger = create_logger('K8s REST endpoint')


@k8s_router.get("/{blue_id}")
def get_blueprint_obj_byID(id_):
    return pickle.loads(db.findone_DB("blueprint_slice_intent", {"id": id_})['blueprint_object'])


@k8s_router.post("/{blue_id}, status", status_code=202, callbacks=callback_router.routes)
def post(blue_id: str, msg: dict):
    try:
        k8s_blue = get_blueprint_obj_byID(blue_id)
        if not k8s_blue:
            raise HTTPException(status_code=404, detail="K8s blueprint {} not found".format(blue_id))
        if k8s_blue._type != "k8s":
            raise HTTPException(status_code=405, detail="blueprint {} is not a Kubernetes cluster".format(blue_id))

        r = k8s_blue.onboard_k8s_cluster({})

        if r:
            return r
        else:
            raise HTTPException(status_code=400, detail="Failed onboarding the K8s cluster {} onto the NFVO"
                                .format(blue_id))

    except Exception:
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=400, detail="Failed onboarding the K8s cluster {}"
                            .format(blue_id))
