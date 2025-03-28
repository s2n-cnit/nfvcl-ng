from nfvcl_models.blueprint_ng.free5gc.free5gcCore import Free5gcCoreConfig

default_core_config: Free5gcCoreConfig = Free5gcCoreConfig.model_validate(
    {
        "global": {
            "name": "free5gc",
            "userPlaneArchitecture": "single",
            "cert": False,
            "nrf": {
                "service": {
                    "name": "nrf-nnrf",
                    "type": "ClusterIP",
                    "port": "8000",
                    "nodePort": "30800"
                }
            },
            "sbi": {
                "scheme": "http"
            },
            "amf": {
                "n2if": {
                    "ipAddress": "0.0.0.0"
                },
                "service": {
                    "ngap": {
                        "enabled": False,
                        "name": "amf-n2",
                        "port": 38412,
                        "nodeport": 31412,
                        "protocol": "SCTP",
                        "type": "LoadBalancer"
                    }
                }
            },
            "smf": {
                "n4if": {
                    "ipAddress": "0.0.0.0"
                }
            },
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
            "n4network": {
                "enabled": False,
                "name": "n4network",
                "type": "macvlan",
                "masterIf": "ens4",
                "subnetIP": "10.180.0.0",
                "cidr": 16,
                "gatewayIP": None,
                "excludeIP": None
            },
            "n6network": {
                "enabled": False,
                "name": "n6network",
                "type": "ipvlan",
                "masterIf": "ens4",
                "subnetIP": "10.180.0.0",
                "cidr": 16,
                "gatewayIP": None,
                "excludeIP": None
            },
            "n9network": {
                "enabled": False,
                "name": "n9network",
                "type": "ipvlan",
                "masterIf": "ens4",
                "subnetIP": "10.180.0.0",
                "cidr": 16,
                "gatewayIP": None,
                "excludeIP": None
            }
        },
        "deployMongoDb": True,
        "deployAmf": True,
        "deployAusf": True,
        "deployN3iwf": False,
        "deployNrf": True,
        "deployNef": True,
        "deployNssf": True,
        "deployPcf": True,
        "deploySmf": True,
        "deployUdm": True,
        "deployUdr": True,
        "deployUpf": False,
        "deployWebui": True,
        "deployDbPython": True,
        "free5gc-nrf": {
            "db": {
                "enabled": False
            },
            "nrf": {
                "configuration": {
                    "oauthConfiguration": {
                        "oauth": False
                    },
                    "configuration": {
                        "DefaultPlmnId": {
                            "mcc": "001",
                            "mnc": "01"
                        }
                    },
                    "logger": {
                        "enable": True,
                        "level": "debug",
                        "reportCaller": False
                    }
                }
            }
        },
        "mongodb": {
            "fullnameOverride": "mongodb",
            "useStatefulSet": True,
            "auth": {
                "enabled": False
            },
            "persistence": {
                "enabled": False,
                "size": "6Gi",
                "mountPath": "/bitnami/mongodb/data/db/"
            },
            "service": {
                "name": "mongodb",
                "type": "LoadBalancer",
                "port": 27017,
                "nodePort": "30017"
            }
        },
        "free5gc-amf": {
            "amf": {
                "configuration": {
                    "configuration": {
                        "amfName": "AMF",
                        "servedGuamiList": [
                            {
                                "plmnId": {
                                    "mcc": "001",
                                    "mnc": "01"
                                },
                                "amfId": "cafe00"
                            }
                        ],
                        "supportTaiList": [
                            {
                                "plmnId": {
                                    "mcc": "001",
                                    "mnc": "01"
                                },
                                "tac": "000000"
                            }
                        ],
                        "plmnSupportList": [
                            {
                                "plmnId": {
                                    "mcc": "001",
                                    "mnc": "01"
                                },
                                "snssaiList": [
                                    {
                                        "sst": 1,
                                        "sd": "000001"
                                    }
                                ]
                            }
                        ],
                        "supportDnnList": [
                            "internet"
                        ],
                        "locality": "area1",
                    },
                    "logger": {
                        "enable": True,
                        "level": "debug",
                        "reportCaller": False
                    }
                }
            }
        },
        "free5gc-smf": {
            "smf": {
                "service": {
                    "type": "ClusterIP",
                    "port": 80
                },
                "configuration": {
                    "configuration": {
                        "smfName": "SMF",
                        "snssaiInfos": [
                            {
                                "sNssai": {
                                    "sst": 1,
                                    "sd": "000001"
                                },
                                "dnnInfos": [
                                    {
                                        "dnn": "internet",
                                        "dnaiList": [
                                            "mec"
                                        ],
                                        "dns": {
                                            "ipv4": "8.8.8.8"
                                        }
                                    }
                                ]
                            }
                        ],
                        "plmnList": [
                            {
                                "mcc": "001",
                                "mnc": "01"
                            }
                        ],
                        "userplaneInformation": {
                            "upNodes": {
                                "gNB1": {
                                    "type": "AN"
                                },
                                "UPF": {
                                    "type": "UPF",
                                    "nodeID": "10.180.1.252",
                                    "addr": "10.180.1.252",
                                    "sNssaiUpfInfos": [
                                        {
                                            "sNssai": {
                                                "sst": 1,
                                                "sd": "000001"
                                            },
                                            "dnnUpfInfoList": [
                                                {
                                                    "dnn": "internet",
                                                    "pools": [
                                                        {
                                                            "cidr": "10.1.0.0/17"
                                                        }
                                                    ]
                                                }
                                            ]
                                        }
                                    ],
                                    "interfaces": [
                                        {
                                            "interfaceType": "N3",
                                            "endpoints": [
                                                "10.180.1.252"
                                            ],
                                            "networkInstances": [
                                                "internet"
                                            ]
                                        }
                                    ]
                                }
                            },
                            "links": [
                                {
                                    "A": "gNB1",
                                    "B": "UPF"
                                }
                            ]
                        },
                        "locality": "area1"
                    },
                    "logger": {
                        "enable": True,
                        "level": "debug",
                        "reportCaller": False
                    }
                }
            }
        },
        "free5gc-ausf": {
            "ausf": {
                "configuration": {
                    "configuration": {
                        "plmnSupportList": [
                            {
                                "mcc": "001",
                                "mnc": "01"
                            }
                        ]
                    },
                    "logger": {
                        "enable": True,
                        "level": "debug",
                        "reportCaller": False
                    }
                }
            }
        },
        "free5gc-nssf": {
            "nssf": {
                "configuration": {
                    "configuration": {
                        "nssfName": "NSSF",
                        "supportedPlmnList": [
                            {
                                "mcc": "001",
                                "mnc": "01"
                            }
                        ],
                        "supportedNssaiInPlmnList": [
                            {
                                "plmnId": {
                                    "mcc": "001",
                                    "mnc": "01"
                                },
                                "supportedSnssaiList": [
                                    {
                                        "sst": 1,
                                        "sd": "000001"
                                    }
                                ]
                            }
                        ],
                        "nsiList": [
                            {
                                "snssai": {
                                    "sst": 1,
                                    "sd": "000001"
                                },
                                "nsiInformationList": [
                                    {
                                        "nrfId": "http://nrf-nnrf:8000/nnrf-nfm/v1/nf-instances",
                                        "nsiId": 10
                                    }
                                ]
                            }
                        ],
                        "taList": [
                            {
                                "tai": {
                                    "plmnId": {
                                        "mcc": "001",
                                        "mnc": "01"
                                    },
                                    "tac": "000000"
                                },
                                "accessType": "3GPP_ACCESS",
                                "supportedSnssaiList": [
                                    {
                                        "sst": 1,
                                        "sd": "000001"
                                    }
                                ]
                            }
                        ]
                    },
                    "logger": {
                        "enable": True,
                        "level": "debug",
                        "reportCaller": False
                    }
                }
            }
        },
        "free5gc-pcf": {
            "pcf": {
                "configuration": {
                    "configuration": {
                        "pcfName": "PCF",
                        "timeFormat": "2019-01-02 15:04:05",
                        "defaultBdtRefId": "BdtPolicyId-",
                        "locality": "area1"
                    },
                    "logger": {
                        "enable": True,
                        "level": "debug",
                        "reportCaller": False
                    }
                }
            }
        },
        "free5gc-udm": {
            "udm": {
                "configuration": {
                    "configuration": {
                        "SuciProfile": [
                            {
                                "ProtectionScheme": 1,
                                "PrivateKey": "c53c22208b61860b06c62e5406a7b330c2b577aa5558981510d128247d38bd1d",
                                "PublicKey": "5a8d38864820197c3394b92613b20b91633cbd897119273bf8e4a6f4eec0a650"
                            },
                            {
                                "ProtectionScheme": 2,
                                "PrivateKey": "F1AB1074477EBCC7F554EA1C5FC368B1616730155E0041AC447D6301975FECDA",
                                "PublicKey": "0472DA71976234CE833A6907425867B82E074D44EF907DFB4B3E21C1C2256EBCD15A7DED52FCBB097A4ED250E036C7B9C8C7004C4EEDC4F068CD7BF8D3F900E3B4"
                            }
                        ]
                    },
                    "logger": {
                        "enable": True,
                        "level": "debug",
                        "reportCaller": False
                    }
                }
            }
        },
        "free5gc-udr": {
            "udr": {
                "configuration": {
                    "logger": {
                        "enable": True,
                        "level": "debug",
                        "reportCaller": False
                    }
                }
            }
        },
        "free5gc-chf": {
            "chf": {
                "configuration": {
                    "logger": {
                        "enable": True,
                        "level": "debug",
                        "reportCaller": False
                    }
                }
            }
        },
        "free5gc-nef": {
            "nef": {
                "configuration": {
                    "logger": {
                        "enable": True,
                        "level": "debug",
                        "reportCaller": False
                    }
                }
            }
        }

    })
