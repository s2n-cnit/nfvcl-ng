from nfvcl_models.blueprint_ng.ueransim_k8s.ueransim_models import UeransimK8sModel

ueransimk8s_default_config: UeransimK8sModel = UeransimK8sModel.model_validate({
    "global": {
        "n2network": {
            "enabled": False,
            "name": "n2network",
            "type": "macvlan",
            "masterIf": "ens4",
            "subnetIP": "10.180.0.0",
            "cidr": 16,
            "gatewayIP": None,
            "excludeIP": None
        },
        "n3network": {
            "enabled": False,
            "name": "n3network",
            "type": "macvlan",
            "masterIf": "ens4",
            "subnetIP": "10.180.0.0",
            "cidr": 16,
            "gatewayIP": None,
            "excludeIP": None
        },
        "image": {
            "name": "gradiant/ueransim",
            "tag": "3.2.7",
            "pullPolicy": "IfNotPresent"
        }
    },
    "gnb": {
        "additional_routes": [],
        "enabled": True,
        "name": "gnb",
        "n2if": {
            "ipAddress": "10.180.255.30"
        },
        "n3if": {
            "ipAddress": "10.180.255.31"
        },
        "amf": {
            "n2if": {
                "ipAddress": "10.180.255.25",
                "port": 38412
            },
            "service": {
                "ngap": {
                    "enabled": True
                }
            }
        },
        "configuration": {
            "mcc": "001",
            "mnc": "01",
            "nci": "0x000000010",
            "idLength": 32,
            "tac": 1,
            "slices": [
                {
                    "sst": 1,
                    "sd": "000001"
                }
            ],
            "ignoreStreamIds": True
        },
        "service": {
            "name": "gnb-service",
            "type": "LoadBalancer",
            "port": 4997,
            "protocol": "UDP"
        }
    },
    "ue": {
        "enabled": True,
        "instances": [
            {
                "name": "ue1",
                "configmap": {
                    "name": "ue1-configmap"
                },
                "volume": {
                    "name": "ue1-volume",
                    "mount": "/ueransim/config"
                },
                "configuration": {
                    "supi": "imsi-001010000000001",
                    "mcc": "001",
                    "mnc": "01",
                    "protectionScheme": 0,
                    "homeNetworkPublicKey": '5a8d38864820197c3394b92613b20b91633cbd897119273bf8e4a6f4eec0a650',
                    "homeNetworkPublicKeyId": 1,
                    "routingIndicator": "0000",
                    "key": "814BCB2AEBDA557AEEF021BB21BEFE25",
                    "op": "9B5DA0D4EC1E2D091A6B47E3B91D2496",
                    "opType": "OPC",
                    "amf": "8000",
                    "imei": "356938035643803",
                    "imeiSv": "4370816125816151",
                    "uacAic": {
                        "mps": False,
                        "mcs": False
                    },
                    "uacAcc": {
                        "normalClass": 0,
                        "class11": False,
                        "class12": False,
                        "class13": False,
                        "class14": False,
                        "class15": False
                    },
                    "sessions": [
                        {
                            "type": "IPv4",
                            "apn": "internet",
                            "slice": {
                                "sst": 1,
                                "sd": "000001"
                            }
                        }
                    ],
                    "configured-nssai": [
                        {
                            "sst": 1,
                            "sd": "000001"
                        }
                    ],
                    "default-nssai": [
                        {
                            "sst": 1,
                            "sd": "000001"
                        }
                    ],
                    "integrity": {
                        "IA1": True,
                        "IA2": True,
                        "IA3": True
                    },
                    "ciphering": {
                        "EA1": True,
                        "EA2": True,
                        "EA3": True
                    },
                    "integrityMaxRate": {
                        "uplink": "full",
                        "downlink": "full"
                    }
                }
            }
        ]
    }
})
