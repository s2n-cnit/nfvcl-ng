from __future__ import annotations

from typing import List

from pydantic import Field

from nfvcl_models.blueprint_ng.g5.ue import UESim
from nfvcl_core_models.base_model import NFVCLBaseModel
from nfvcl_models.blueprint_ng.blueprint_ueransim_model import UeransimArea, UeransimConfig, UeransimUe
from nfvcl_core_models.blueprints.blueprint import BlueprintNGCreateModel


class UeransimBlueprintRequestInstance(BlueprintNGCreateModel):
    config: UeransimConfig
    areas: List[UeransimArea] = Field(
        ...,
        description='list of areas to instantiate the Blueprint',
        min_length=1
    )

    class Config:
        use_enum_values = True
        """schema_extra = {
            "example":
            {
                "type": "UeRanSim",
                "config": {
                    "network_endpoints": {
                        "mgt": "control",
                        "wan": "control"
                    }
                },
                "areas": [
                    {
                        "id": 3,
                        "nci": "0x00000024",
                        "idLength": 32,
                        "ues": [
                            {
                                "id": 1,
                                "sims": [
                                    {
                                        "imsi": "001010000000002",
                                        "plmn": "00101",
                                        "key": "465B5CE8B199B49FAA5F0A2EE238A6BC",
                                        "op": "E8ED289DEBA952E4283B54E88E6183CA",
                                        "opType": "OPC",
                                        "amf": "8000",
                                        "configured_nssai": [{"sst": 1, "sd": 1}],
                                        "default_nssai": [{"sst": 1, "sd": 1}],
                                        "sessions": [
                                            {
                                                "type": "IPv4",
                                                "apn": "internet",
                                                "slice": {"sst": 1, "sd": 1}
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                ]

            }
        }"""



class UeransimBlueprintRequestAddDelGNB(NFVCLBaseModel):
    area_id: str = Field()


class UeransimBlueprintRequestAddUE(NFVCLBaseModel):
    area_id: str = Field()
    ue: UeransimUe = Field()


class UeransimBlueprintRequestDelUE(NFVCLBaseModel):
    area_id: str = Field()
    ue_id: int = Field()


class UeransimBlueprintRequestAddSim(NFVCLBaseModel):
    area_id: str = Field()
    ue_id: int = Field()
    sim: UESim = Field()

class UeransimBlueprintRequestDelSim(NFVCLBaseModel):
    area_id: str = Field()
    ue_id: int = Field()
    imsi: str = Field()


class UeransimBlueprintRequestAddDelUe(NFVCLBaseModel):
    areas: List[UeransimArea] = Field(
        ...,
        description='List of areas with devices to be added',
        min_length=1
    )

    class Config:
        use_enum_values = True
        """schema_extra = {
            "example":
            {
                "type": "UeRanSim",
                "areas": [
                    {
                        "id": 3,
                        "ues": [
                            {
                                "id": 1,
                                "sims": [
                                    {
                                        "imsi": "001010000000002",
                                        "plmn": "00101",
                                        "key": "465B5CE8B199B49FAA5F0A2EE238A6BC",
                                        "op": "E8ED289DEBA952E4283B54E88E6183CA",
                                        "opType": "OPC",
                                        "amf": "8000",
                                        "configured_nssai": [{"sst": 1, "sd": 1}],
                                        "default_nssai": [{"sst": 1, "sd": 1}],
                                        "sessions": [
                                            {
                                                "type": "IPv4",
                                                "apn": "internet",
                                                "slice": {"sst": 1, "sd": 1}
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                ]

            }
        }"""
