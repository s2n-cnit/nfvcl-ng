from blueprints.blue_5g_base.models import Create5gModel, AddTacModel
from typing import Literal, Optional


# =============================================== main section for blue free5gc k8s model class========================

class Free5gck8sBlueCreateModel(Create5gModel):
    type: Literal["Free5GC_K8s"]

class Free5gck8sBlueUpdateModel(Free5gck8sBlueCreateModel):
    operation: Literal["add_tac", "del_tac", "add_ues", "del_ues", "add_slice", "del_slice", "monitor", "log"]

class Free5gck8sTacModel(AddTacModel):
    type: Literal["Free5GC_K8s"]
    operation: Optional[Literal["add_tac", "del_tac"]]

class Free5gck8sSliceModel(AddTacModel):
    type: Literal["Free5GC_K8s"]
    operation: Optional[Literal["add_slice", "del_slice"]]

class Free5gck8sSubscriberModel(AddTacModel):
    type: Literal["Free5GC_K8s"]
    operation: Optional[Literal["add_ues", "del_ues"]]
# =========================================== End of main section =====================================================
