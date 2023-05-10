import copy

from models.network import NetworkModel, RouterModel, PduModel
from models.vim import VimModel
from models.k8s.k8s_models import K8sModel
from pydantic import BaseModel, HttpUrl
from typing import List, Optional


class TopologyModel(BaseModel):
    id: Optional[str] = "topology"
    callback: Optional[HttpUrl] = None
    vims: List[VimModel] = []
    kubernetes: List[K8sModel] = []
    networks: List[NetworkModel] = []
    routers: List[RouterModel] = []
    pdus: List[PduModel] = []

    def to_dict(self) -> dict:
        """
        Return a dictionary. This avoids error when trying to convert this object into json because some data type does
        not support conversion.

        Returns:
            a dictionary representation
        """
        to_return = copy.deepcopy(self)
        for i in range(0,len(to_return.networks)):
            to_return.networks[i] = to_return.networks[i].to_dict()
        return to_return.dict()