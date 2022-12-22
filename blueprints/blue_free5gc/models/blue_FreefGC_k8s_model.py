from blueprints.blue_5g_base.models import Create5gModel
from typing import Literal


# =============================================== main section for blue free5gc k8s model class========================

class Free5gck8sBlueCreateModel(Create5gModel):
    type: Literal["Free5GC_K8s"]

class Free5gck8sBlueUpdateModel(Free5gck8sBlueCreateModel):
    operation: Literal["add_tac", "del_tac", "add_ues", "del_ues", "add_slice", "del_slice", "monitor", "log"]
# =========================================== End of main section =====================================================
