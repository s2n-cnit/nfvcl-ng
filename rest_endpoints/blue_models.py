from blueprints.blue_k8s.models import K8sBlueprintCreate, K8sBlueprintScale
from blueprints.blue_5g_base.models import Create5gModel
from blueprints.blue_free5gc.models import Free5gck8sBlueCreateModel, Free5gck8sBlueUpdateModel
from blueprints.blue_mqtt.models import MqttRequestBlueprintInstance
from blueprints.blue_trex.models import TrexRequestBlueprintInstance
from blueprints.blue_ueransim.models import UeranSimBlueprintRequestInstance
from blueprints.blue_vo.models import VoBlueprintRequestInstance
from blueprints.blue_vyos.models import VyOSBlueprintCreate
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
