from enum import Enum
from ipaddress import IPv4Address
from typing import Optional, List
from pydantic import Field
from models.base_model import NFVCLBaseModel


class Cni(Enum):
    flannel = 'flannel'
    calico = 'calico'


class LbType(Enum):
    layer2 = 'layer2'
    layer3 = 'layer3'


class LBPool(NFVCLBaseModel):
    mode: LbType = Field(
        'layer2', description='Operating mode of Metal-LB. Default Layer-2.'
    )
    net_name: str = Field(
        ..., description='name of the network in the topology'
    )
    ip_start: Optional[str] = Field(default=None)
    ip_end: Optional[str] = Field(default=None)
    range_length: Optional[int] = Field(None,description='Number of IPv4 addresses to reserved if no ip start'
                                                         ' and end are passed. Default 10 addresses.')

    def get_ip_address_list(self, max_num: int = 256) -> List[str]:
        """
        Retrieve a list of IP addresses in the pool. It is possible to limit the number of IPs using the function parameter
        Args:
            max_num: The maximum number of IPs retrieved in the list

        Returns:
            A list of IP addresses in the list
        """
        ip_list: List[str] = []
        ip_s = IPv4Address(self.ip_start)
        ip_e = IPv4Address(self.ip_end)

        for i in range(max_num):
            ip_list.append((ip_s+i).exploded)
            if ip_s+i == ip_e:
                break

        assert len(ip_list)>0
        return ip_list

    class Config:
        use_enum_values = True
