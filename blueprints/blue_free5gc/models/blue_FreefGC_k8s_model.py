from blueprints.blue_5g_base.models import Create5gModel
from typing import Literal


# =============================================== main section for blue free5gc k8s model class========================

class Free5gck8sBlueCreateModel(Create5gModel):
    type: Literal["Free5GC"]

# =========================================== End of main section =====================================================
