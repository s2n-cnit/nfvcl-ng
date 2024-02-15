from __future__ import annotations

import abc
import copy
import importlib
import json
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, List, Any, Dict, Callable, TypeVar, Generic

from fastapi import APIRouter
from pydantic import Field, SerializeAsAny, create_model
from typing_extensions import Literal

from models.base_model import NFVCLBaseModel
from models.k8s.k8s_objects import K8sService

StateTypeVar = TypeVar("StateTypeVar")
ProviderDataTypeVar = TypeVar("ProviderDataTypeVar")
CreateConfigTypeVar = TypeVar("CreateConfigTypeVar")


def get_class_from_path(class_path: str):
    field_type_splitted = class_path.split(".")

    module_name = ".".join(field_type_splitted[:-1])
    class_name = field_type_splitted[-1]

    module = importlib.import_module(module_name)
    CorrectClass = getattr(module, class_name)
    return CorrectClass


class BlueprintNGStatus(NFVCLBaseModel):
    error: bool = Field(default=False)
    current_operation: str = Field(default="")
    detail: str = Field(default="")


class BlueprintNGCreateModel(NFVCLBaseModel):
    pass


class RegisteredResource(NFVCLBaseModel):
    type: str = Field()
    value: SerializeAsAny[Resource] = Field()


class BlueprintNGBaseModel(NFVCLBaseModel, Generic[StateTypeVar, ProviderDataTypeVar, CreateConfigTypeVar]):
    id: str = Field()
    type: str = Field()
    # TODO provare a mettere un serializzatore di modello sullo stato (quello generico) e serializzare a mano i campi
    registered_resources: Dict[str, RegisteredResource] = Field(default={})

    state_type: str = Field()
    state: StateTypeVar = Field()  # TODO questa è la running-config
    create_config_type: str = Field()
    create_config: CreateConfigTypeVar = Field()
    created: Optional[datetime] = Field(default=None)
    status: BlueprintNGStatus = Field(default=BlueprintNGStatus())

    # TODO il tipo dovrebbe essere PrometheusTargetModel
    node_exporters: List[str] = Field(default=[], description="List of node exporters (for prometheus) active in the blueprint.")

    provider_type: str = Field()
    provider_data_type: str = Field()
    provider_data: ProviderDataTypeVar = Field()

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**self.fix_types(["state", "provider_data", "create_config"], **kwargs))

    def fix_types(self, field_names: List[str], **kwargs: Any):
        for field_name in field_names:
            field_value = kwargs[field_name]
            if isinstance(field_value, dict):
                kwargs[field_name] = get_class_from_path(kwargs[f"{field_name}_type"]).model_validate(field_value)
        return kwargs


class HttpRequestType(Enum):
    GET = "GET"
    POST = "POST"


class BlueprintNGState(NFVCLBaseModel):
    last_update: Optional[datetime] = Field(default=None)


class BlueprintNG(Generic[StateTypeVar, ProviderDataTypeVar, CreateConfigTypeVar]):
    base_model: BlueprintNGBaseModel[StateTypeVar, ProviderDataTypeVar, CreateConfigTypeVar]
    api_router: APIRouter
    provider: BlueprintNGProviderInterface

    def __init__(self, provider_type: type[BlueprintNGProviderInterface], state_type: type[BlueprintNGState], db_data: Optional[str] = None):
        super().__init__()
        self.provider = provider_type()
        self.state_type = state_type
        if db_data is not None:
            self.base_model = BlueprintNGBaseModel.model_validate_json(db_data)
        else:
            state = state_type()
            self.base_model = BlueprintNGBaseModel[StateTypeVar, ProviderDataTypeVar, CreateConfigTypeVar](
                id=str(uuid.uuid4()),
                type=f"{self.__class__.__qualname__}",
                state_type=f"{state.__class__.__module__}.{state.__class__.__qualname__}",
                state=state,
                provider_type=self.provider.__class__.__qualname__,
                provider_data_type=f"{self.provider.data.__class__.__module__}.{self.provider.data.__class__.__qualname__}",
                provider_data=self.provider.data,
                create_config=BlueprintNGCreateModel(),
                create_config_type=f"{BlueprintNGCreateModel.__module__}.{BlueprintNGCreateModel.__qualname__}"
            )

    def register_resource(self, resource: Resource):
        if not resource.id:
            resource.id = str(uuid.uuid4())
        resource.set_context(self)
        self.base_model.registered_resources[resource.id] = RegisteredResource(type=f"{resource.__class__.__module__}.{resource.__class__.__qualname__}", value=resource)

    def init_blueprint_type(self):
        self.api_router = APIRouter(
            prefix="/{}".format(self.__name__),
            tags=["Blueprint {}".format(self.__name__)],
            responses={404: {"description": "Not found"}}
        )

    def register_api(self, path: str, request_type: HttpRequestType, method: Callable):
        self.api_router.add_api_route(path, method, methods=[request_type.value])

    def create(self, create_model: BlueprintNGCreateModel):
        pass

    def destroy(self):
        pass

    @property
    def state(self) -> StateTypeVar:
        return self.base_model.state

    @property
    def create_config(self) -> CreateConfigTypeVar:
        return self.base_model.create_config

    @property
    def provider_data(self) -> ProviderDataTypeVar:
        return self.base_model.provider_data

    def find_resource_occurrences(self, obj, tipo, path=()):
        occurrences = []

        if isinstance(obj, tipo):
            occurrences.append(path)

        if isinstance(obj, dict):
            for key, value in obj.items():
                occurrences.extend(self.find_resource_occurrences(value, tipo, path + (key,)))
        elif isinstance(obj, list):
            for idx, item in enumerate(obj):
                occurrences.extend(self.find_resource_occurrences(item, tipo, path + (idx,)))
        elif hasattr(obj, '__dict__'):
            for attr_name in vars(obj):
                attr_value = getattr(obj, attr_name)
                occurrences.extend(self.find_resource_occurrences(attr_value, tipo, path + (attr_name,)))

        return occurrences

    def find_REF_occurrences(self, obj, path=()):
        occurrences = []

        if isinstance(obj, str) and obj.startswith('REF='):
            occurrences.append(path)

        if isinstance(obj, dict):
            for key, value in obj.items():
                occurrences.extend(self.find_REF_occurrences(value, path + (key,)))
        elif isinstance(obj, list):
            for idx, item in enumerate(obj):
                occurrences.extend(self.find_REF_occurrences(item, path + (idx,)))
        elif hasattr(obj, '__dict__'):
            for attr_name in vars(obj):
                attr_value = getattr(obj, attr_name)
                occurrences.extend(self.find_REF_occurrences(attr_value, path + (attr_name,)))

        return occurrences

    def override_variables_in_dict(self, example_obj, obj_dict, tipo):
        occ = self.find_resource_occurrences(example_obj, tipo)

        for path in sorted(occ, key=lambda x: len(x), reverse=True):
            current = obj_dict
            for key in path[:-1]:
                current = current[key]
            current[path[-1]] = f'REF={current[path[-1]]["id"]}'

    def override_variables_in_dict_REF(self, example_obj, obj_dict, registered_resource):
        occ = self.find_REF_occurrences(example_obj)
        for path in sorted(occ, key=lambda x: len(x), reverse=True):
            current = obj_dict
            for key in path[:-1]:
                current = current[key]
            current[path[-1]] = registered_resource[current[path[-1]].split("REF=")[1]].value

    def to_db(self):
        aaa = self.base_model.model_dump()

        self.override_variables_in_dict(self.base_model.state, aaa["state"], Resource)
        for chiave, valore in self.base_model.registered_resources.items():
            if isinstance(valore.value, ResourceConfiguration):
                self.override_variables_in_dict(valore.value, aaa["registered_resources"][chiave]["value"], ResourceDeployable)

        return json.dumps(aaa, indent=4)

    def from_db(self, serialized: str):
        deserialized_dict = json.loads(serialized)

        deserialized_dict_edited = copy.deepcopy(deserialized_dict)
        del deserialized_dict_edited["registered_resources"]
        deserialized_dict_edited["state"] = self.state_type().model_dump()
        self.base_model = BlueprintNGBaseModel[StateTypeVar, ProviderDataTypeVar, CreateConfigTypeVar].model_validate(deserialized_dict_edited)

        for resource_id, resource in deserialized_dict["registered_resources"].items():
            if resource["value"]["type"] == "ResourceDeployable":
                self.register_resource(get_class_from_path(resource["type"]).model_validate(resource["value"]))

        for resource_id, resource in deserialized_dict["registered_resources"].items():
            if resource["value"]["type"] == "ResourceConfiguration":
                self.override_variables_in_dict_REF(resource["value"], resource["value"], self.base_model.registered_resources)
                self.register_resource(get_class_from_path(resource["type"]).model_validate(resource["value"]))


        self.override_variables_in_dict_REF(deserialized_dict["state"], deserialized_dict["state"], self.base_model.registered_resources)

        self.base_model.state = self.state_type.model_validate(deserialized_dict["state"])
        return self.base_model.state


class Resource(NFVCLBaseModel):
    _context: Optional[BlueprintNG]
    id: Optional[str] = Field(default=None)
    type: Literal['Resource'] = "Resource"

    def set_context(self, context: BlueprintNG):
        self._context = context

    def get_context(self):
        return self._context


class ResourceDeployable(Resource):
    """
    Represents a VM, Helm Chart or PDU
    """
    type: Literal['ResourceDeployable'] = "ResourceDeployable"
    area: str = Field()
    name: str = Field()


class ResourceConfiguration(Resource):
    """
    Represents a configuration for a Resource
    """
    type: Literal['ResourceConfiguration'] = "ResourceConfiguration"
    pass


class VmResourceImage(NFVCLBaseModel):
    """
    Represents a VM Image

    Attributes:
        name (str): The name of the VM image.
        url (str, optional): The URL from witch the image is downloaded if necessary.
    """
    name: str = Field()
    url: Optional[str] = Field(default=None)


class VmResourceFlavor(NFVCLBaseModel):
    memory_mb: str = Field(default="8192", alias='memory-mb', description="Should be a multiple of 1024")
    storage_gb: str = Field(default="32", alias='storage-gb')
    vcpu_count: str = Field(default="4", alias='vcpu-count')


class VmResource(ResourceDeployable):
    """
    Represent a VM Resource to BE instantiated

    Attributes:
        id (str): The id of the VM Resource
        name (str): The name of the VM
        image (VmResourceImage): The image of the VM
        username (str): The username of the VM
        password (str): The password of the VM
        become_password (str): The password to be used in the VM to get admin power
        management_network (str): name of the management network attached to VM (like OS network)
        additional_networks (List[str]): name list of network attached to VM (like OS network)
        network_interfaces (List[Any]): list of network interfaces attached to the VM that includes IP, MAC, port sec, ...
        state (str): running, stopped, initializated,
    """
    image: VmResourceImage = Field()
    flavor: VmResourceFlavor = Field()
    username: str = Field()
    password: str = Field()
    become_password: Optional[str] = Field(default=None)
    management_network: str = Field()
    additional_networks: List[str] = Field(default=[])

    # Potrebbe mettersi la data di creazione
    created: bool = Field(default=False)
    # TODO il tipo deve essere la rappresentazione dell'interfaccia di OS, con IP, mac, nome, port sec, gateway ...
    network_interfaces: Optional[Dict[str, Any]] = Field(default=None)
    # TODO accesa, spenta, in inizializzazione..., cambiare tipo con enum
    state: Optional[str] = Field(default=None)

    def create(self):
        self.get_context().provider.create_vm(self)


class VmResourceConfiguration(ResourceConfiguration):
    vm_resource: VmResource = Field()

    def configure(self):
        if not self.vm_resource.created:
            # TODO change type
            raise Exception("VM Resource not created")
        self.get_context().provider.configure_vm(self)


class VmResourceAnsibleConfiguration(VmResourceConfiguration):

    def dump_playbook(self) -> str:
        print("Esegue dump ansible playbook....")
        return "[[DUMPED PLAYBOOK]]"

    def build_configuration(self, configuration_values: Any):
        print("Costruisco ansible playbook....")


class VmResourceNativeConfiguration(VmResourceConfiguration):
    def run_code(self):
        print("Esegue codice...")


class HelmChartResource(ResourceDeployable):
    chart: str = Field()
    repo: Optional[str] = Field(default=None)
    namespace: str = Field()
    additional_params: Dict[str, Any] = Field()

    created: bool = Field(default=False)
    created_services: Optional[List[K8sService]] = Field(default=None)

    def create(self):
        pass


class K8SResourceConfiguration(ResourceConfiguration):
    def __init__(self, helm_chart_resource: HelmChartResource, values: Dict[str, Any]):
        super().__init__()
        self.helm_chart_resource = helm_chart_resource
        self.values = values

    def configure(self):
        pass


class BlueprintNGProviderData(NFVCLBaseModel):
    pass


class BlueprintNGProviderInterface(abc.ABC):
    data: BlueprintNGProviderData

    @abc.abstractmethod
    def create_vm(self, vm_resource: VmResource):
        pass

    @abc.abstractmethod
    def configure_vm(self, vm_resource_configuration: VmResourceConfiguration):
        pass

    @abc.abstractmethod
    def destroy_vm(self):
        pass

    @abc.abstractmethod
    def install_helm_chart(self):
        pass

    @abc.abstractmethod
    def update_values_helm_chart(self):
        pass

    @abc.abstractmethod
    def uninstall_helm_chart(self):
        pass
