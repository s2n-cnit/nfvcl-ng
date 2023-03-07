from pydantic import Field, BaseModel


class VMFlavors(BaseModel):
    memory_mb: str = Field(16384, alias='memory-mb')
    storage_gb: str = Field(32, alias='storage-gb')
    vcpu_count: str = Field(16, alias='vcpu-count')