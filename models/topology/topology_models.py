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
