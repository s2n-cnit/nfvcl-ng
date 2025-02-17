from pydantic import Field

from nfvcl.models.blueprint_ng.g5.custom_types_5g import SDType, SSTType
from nfvcl_core.models.base_model import NFVCLBaseModel


class Slice5G(NFVCLBaseModel):
    sst: SSTType = Field()
    sd: SDType = Field()

    def sst_as_hex(self):
        return f"0x{self.sst:02x}"

    def sst_as_string(self):
        return self.sst.name

    def sd_as_hex(self):
        return f"0x{self.sd}"

    def sd_as_int(self):
        return int(self.sd, 16)
