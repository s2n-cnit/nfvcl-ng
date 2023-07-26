from enum import Enum


class TopologyEventType(Enum):
    TOPO_CREATE = "create"
    TOPO_DELETE = "delete"
    TOPO_VIM_CREATE = "create_vim"
    TOPO_VIM_DEL = "delete_vim"
    TOPO_VIM_UPDATE = "update_vim"
    TOPO_CREATE_NETWORK = "create_network"
    TOPO_DELETE_NETWORK = "delete_network"
    TOPO_CREATE_ROUTER = "create_router"
    TOPO_DELETE_ROUTER = "delete_router"
    TOPO_CREATE_RANGE_RES = "create_range_reservation"
    TOPO_DELETE_RANGE_RES = "release_range_reservation"
    TOPO_CREATE_PDU = "create_pdu"
    TOPO_DELETE_PDU = "delete_pdu"
    TOPO_CREATE_K8S = "create_k8s_cluster"
    TOPO_DELETE_K8S = "delete_k8s_cluster"
    TOPO_UPDATE_K8S = "update_k8s_cluster"
    TOPO_CREATE_PROM_SRV = "create_prom_srv"
    TOPO_DELETE_PROM_SRV = "delete_prom_srv"
    TOPO_UPDATE_PROM_SRV = "update_prom_srv"
