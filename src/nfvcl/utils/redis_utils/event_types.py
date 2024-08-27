from enum import Enum


class NFVCLEventType(Enum):
    pass


class BlueEventType(NFVCLEventType):
    BLUE_CREATED = "create"
    BLUE_DELETED = "delete"
    BLUE_START_PROCESSING = "start_processing"
    BLUE_END_PROCESSING = "end_processing"
    BLUE_STARTED_DAY0 = "start_day0"
    BLUE_STARTED_DAY2 = "start_day2"
    BLUE_END_DAY2 = "end_day2"
    BLUE_START_DAYN = "start_dayN"
    BLUE_ERROR = "blue_error"


class TopologyEventType(NFVCLEventType):
    TOPO_CREATE = "create"
    TOPO_DELETE = "delete"
    TOPO_VIM_CREATE = "create_vim"
    TOPO_VIM_DEL = "delete_vim"
    TOPO_VIM_UPDATE = "update_vim"
    TOPO_CREATE_NETWORK = "create_network"
    TOPO_DELETE_NETWORK = "delete_network"
    TOPO_CREATED_ROUTER = "create_router"
    TOPO_DELETED_ROUTER = "delete_router"
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


class K8sEventType(NFVCLEventType):
    PLUGIN_INSTALLED = "plugin_installed"
    DEFINITION_APPLIED = "definition_applied"
