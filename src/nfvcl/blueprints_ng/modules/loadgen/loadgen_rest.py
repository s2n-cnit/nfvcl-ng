from enum import Enum
from pydantic import Field, model_validator
from typing import Self

from nfvcl_common.base_model import NFVCLBaseModel


class CpuLoadDistribution(str, Enum):
    EQUAL = "equal"
    SEQUENTIAL = "sequential"


class CpuLoad(NFVCLBaseModel):
    target_percent: float = Field(ge=0, allow_inf_nan=False)
    core_count: int = Field(gt=0)
    distribution: CpuLoadDistribution

    @model_validator(mode="after")
    def validate_capacity(self) -> Self:
        capacity = self.core_count * 100
        if self.target_percent > capacity:
            raise ValueError(
                f"target_percent must not exceed core_count * 100 ({capacity})"
            )
        return self


class RamLoad(NFVCLBaseModel):
    amount_bytes: int = Field(ge=0)


class DiskLoad(NFVCLBaseModel):
    file_path: str
    chunk_size: int = Field(gt=0)
    sleep_ms: int = Field(ge=0)


class DiskUsageLoad(NFVCLBaseModel):
    file_path: str
    amount_bytes: int = Field(ge=0, le=2**64 - 1)


class LoadRequest(NFVCLBaseModel):
    cpu: CpuLoad | None = None
    ram: RamLoad | None = None
    disk_read: DiskLoad | None = None
    disk_write: DiskLoad | None = None
    disk_usage: DiskUsageLoad | None = None
