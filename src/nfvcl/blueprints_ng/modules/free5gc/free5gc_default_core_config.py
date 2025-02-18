from nfvcl_models.blueprint_ng.free5gc.free5gcCore import Free5gcCoreConfig

default_core_config: Free5gcCoreConfig = Free5gcCoreConfig.model_validate(
    {
        "global": {
            "name": "free5gc",
            "userPlaneArchitecture": "ulcl",
            "nrf": {
                "service": {
                    "name": "nrf-nnrf",
                    "type": "LoadBalancer",
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
                        "enabled": True,
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
                    "ipAddress": "10.180.0.28"
                }
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
                    "serviceNameList": [
                        "nnrf-nfm",
                        "nnrf-disc"
                    ],
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
                        "level": "info",
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
                    "serviceNameList": [
                        "namf-comm",
                        "namf-evts",
                        "namf-mt",
                        "namf-loc",
                        "namf-oam"
                    ],
                    "configuration": {
                        "amfName": "AMF",
                        "serviceNameList": [
                            "namf-comm",
                            "namf-evts",
                            "namf-mt",
                            "namf-loc",
                            "namf-oam"
                        ],
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
                        "security": {
                            "integrityOrder": [
                                "NIA2"
                            ],
                            "cipheringOrder": [
                                "NEA0"
                            ]
                        },
                        "networkName": {
                            "full": "free5GC",
                            "short": "free"
                        },
                        "ngapIE": {
                            "mobilityRestrictionList": {
                                "enable": True
                            },
                            "maskedIMEISV": {
                                "enable": True
                            },
                            "redirectionVoiceFallback": {
                                "enable": False
                            }
                        },
                        "nasIE": {
                            "networkFeatureSupport5GS": {
                                "enable": True,
                                "length": 1,
                                "imsVoPS": 0,
                                "emc": 0,
                                "emf": 0,
                                "iwkN26": 0,
                                "mpsi": 0,
                                "emcN3": 0,
                                "mcsi": 0
                            }
                        },
                        "t3502Value": 720,
                        "t3512Value": 3600,
                        "non3gppDeregTimerValue": 3240,
                        "t3513": {
                            "enable": True,
                            "expireTime": "6s",
                            "maxRetryTimes": 4
                        },
                        "t3522": {
                            "enable": True,
                            "expireTime": "6s",
                            "maxRetryTimes": 4
                        },
                        "t3550": {
                            "enable": True,
                            "expireTime": "6s",
                            "maxRetryTimes": 4
                        },
                        "t3560": {
                            "enable": True,
                            "expireTime": "6s",
                            "maxRetryTimes": 4
                        },
                        "t3565": {
                            "enable": True,
                            "expireTime": "6s",
                            "maxRetryTimes": 4
                        },
                        "t3570": {
                            "enable": True,
                            "expireTime": "6s",
                            "maxRetryTimes": 4
                        },
                        "locality": "area1",
                        "sctp": {
                            "numOstreams": 3,
                            "maxInstreams": 5,
                            "maxAttempts": 2,
                            "maxInitTimeout": 2
                        },
                        "defaultUECtxReq": False
                    },
                    "logger": {
                        "enable": True,
                        "level": "info",
                        "reportCaller": False
                    }
                }
            }
        },
        "free5gc-smf": {
            "smf": {
                "configuration": {
                    "serviceNameList": [
                        "nsmf-pdusession",
                        "nsmf-event-exposure",
                        "nsmf-oam"
                    ],
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
                        "locality": "area1",
                        "t3591": {
                            "enable": True,
                            "expireTime": "16s",
                            "maxRetryTimes": 3
                        },
                        "t3592": {
                            "enable": True,
                            "expireTime": "16s",
                            "maxRetryTimes": 3
                        }
                    },
                    "logger": {
                        "enable": True,
                        "level": "info",
                        "reportCaller": False
                    }
                }
            }
        },
        "free5gc-ausf": {
            "ausf": {
                "configuration": {
                    "serviceNameList": [
                        "nausf-auth"
                    ],
                    "configuration": {
                        "plmnSupportList": [
                            {
                                "mcc": "001",
                                "mnc": "01"
                            }
                        ],
                        "groupId": "ausfGroup001",
                        "eapAkaSupiImsiPrefix": False
                    },
                    "logger": {
                        "enable": True,
                        "level": "info",
                        "reportCaller": False
                    }
                }
            }
        },
        "free5gc-nssf": {
            "nssf": {
                "configuration": {
                    "serviceNameList": [
                        "nnssf-nsselection",
                        "nnssf-nssaiavailability"
                    ],
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
                                        "nrfId": "http://nrf-nrrf:8000/nnrf-nfm/v1/nf-instances",
                                        "nsiId": 10
                                    }
                                ]
                            }
                        ],
                        "amfSetList": [
                            {
                                "amfSetId": 1,
                                "nrfAmfSet": "http://nrf-nrrf:8000/nnrf-nfm/v1/nf-instances",
                                "supportedNssaiAvailabilityData": [
                                    {
                                        "tai": {
                                            "plmnId": {
                                                "mcc": "001",
                                                "mnc": "01"
                                            },
                                            "tac": "000000",
                                        },
                                        "supportedSnssaiList": [
                                            {
                                                "sst": 1,
                                                "sd": "000001"
                                            }
                                        ]
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
                        "level": "info",
                        "reportCaller": False
                    }
                }
            }
        },
        "free5gc-pcf": {
            "pcf": {
                "configuration": {
                    "serviceList": [
                        {
                            "serviceName": "npcf-am-policy-control"
                        },
                        {
                            "serviceName": "npcf-smpolicycontrol",
                            "suppFeat": "3fff"
                        },
                        {
                            "serviceName": "npcf-bdtpolicycontrol"
                        },
                        {
                            "serviceName": "npcf-policyauthorization",
                            "suppFeat": "3"
                        },
                        {
                            "serviceName": "npcf-eventexposure"
                        },
                        {
                            "serviceName": "npcf-ue-policy-control"
                        }
                    ],
                    "configuration": {
                        "pcfName": "PCF",
                        "timeFormat": "2019-01-02 15:04:05",
                        "defaultBdtRefId": "BdtPolicyId-",
                        "locality": "area1"
                    },
                    "logger": {
                        "enable": True,
                        "level": "info",
                        "reportCaller": False
                    }
                }
            }
        },
        "free5gc-udm": {
            "udm": {
                "configuration": {
                    "serviceNameList": [
                        "nudm-sdm",
                        "nudm-uecm",
                        "nudm-ueau",
                        "nudm-ee",
                        "nudm-pp"
                    ],
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
                        "level": "info",
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
                        "level": "info",
                        "reportCaller": False
                    }
                }
            }
        },
        "free5gc-chf": {
            "chf": {
                "configuration": {
                    "serviceNameList": [
                        "nchf-convergedcharging"
                    ]
                }
            }
        },
        "free5gc-nef": {
            "nef": {
                "configuration": {
                    "serviceList": [
                        {
                            "serviceName": "nnef-pfdmanagement"
                        },
                        {
                            "serviceName": "nnef-oam"
                        }
                    ]
                },
                "logger": {
                    "enable": True,
                    "level": "info",
                    "reportCaller": False
                }
            }
        }

    })
