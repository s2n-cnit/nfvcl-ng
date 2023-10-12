from typing import List, Optional
from pydantic import Field, BaseModel


class CharmParameter(BaseModel):
    name: str
    value: Optional[str] = Field(default=None)
    default_value: Optional[str] = Field(alias='default-value', default=None)
    data_type: str = Field(alias='data-type', default='STRING')


class CharmPrimitive(BaseModel):
    name: str
    execution_environment_ref: str = Field(alias='execution-environment-ref') #TODO check type
    parameter: List[CharmParameter]
    seq: Optional[str] = Field(default=None)


class JujuCharmName(BaseModel):
    charm: str


class CharmExecEnviron(BaseModel):
    id: str
    helm_chart: Optional[str] = Field(alias='helm-chart', default=None)
    external_connection_point_ref: Optional[str] = Field(alias='external-connection-point-ref', default=None)
    juju: Optional[JujuCharmName] = Field(default=None)


class CharmDay12(BaseModel):
    id: str
    config_primitive: List[CharmPrimitive] = Field(alias='config-primitive')
    execution_environment_list: List = Field(alias='execution-environment-list')
    initial_config_primitive: List = Field(alias='initial-config-primitive')


class OperateVnfOpConfig(BaseModel):
    day12: List[CharmDay12] = Field(alias='day1-2')


class LCMOperationConfig(BaseModel):
    operate_vnf_op_config: OperateVnfOpConfig = Field(alias='operate-vnf-op-config')