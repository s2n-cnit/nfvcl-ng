# TODO move models relative to specific k8s blueprint back to the blueprint folder.
from nfvcl.models.k8s.blueprint_k8s_model import K8sBlueprintCreate, K8sBlueprintScale
from nfvcl.blueprints.blue_5g_base.models import Create5gModel
from nfvcl.blueprints.blue_free5gc.models import Free5gck8sBlueCreateModel, Free5gck8sBlueUpdateModel
from nfvcl.blueprints.blue_mqtt.models import MqttRequestBlueprintInstance
from nfvcl.blueprints.blue_trex.models import TrexRequestBlueprintInstance
from nfvcl.blueprints.blue_ueransim.models import UeranSimBlueprintRequestInstance
from nfvcl.blueprints.blue_vo.models import VoBlueprintRequestInstance
from nfvcl.blueprints.blue_vyos.models import VyOSBlueprintCreate
from typing import Union

blue_create_models = Union[
    K8sBlueprintCreate,
    Create5gModel,
    Free5gck8sBlueCreateModel,
    MqttRequestBlueprintInstance,
    TrexRequestBlueprintInstance,
    UeranSimBlueprintRequestInstance,
    VoBlueprintRequestInstance,
    VyOSBlueprintCreate
]

blue_day2_models = Union[
    K8sBlueprintScale,
    Free5gck8sBlueUpdateModel
]
