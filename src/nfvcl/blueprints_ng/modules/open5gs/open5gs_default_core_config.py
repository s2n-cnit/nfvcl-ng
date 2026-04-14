from nfvcl_models.blueprint_ng.open5gs.core import Open5gsCoreConfig

default_core_config: Open5gsCoreConfig = Open5gsCoreConfig.model_validate({
    "dbURI": "mongodb://open5gs-mongodb/open5gs",
    "populate": {
        "enabled": False,
        "image": {
            "registry": "docker.io",
            "repository": "gradiant/open5gs-dbctl",
            "tag": "0.10.3",
            "pullPolicy": "IfNotPresent"
        },
        "initCommands": []
    },
    "mongodb": {
        "enabled": True,
        "auth": {
            "enabled": False
        }
    },
    "smf": {
        "enabled": True,
        "config": {
            "pfcp": {
                "dev": "eth0"
            },
            "logLevel": "debug",
            "sbi": {
                "client": {
                    "nrf": {
                        "enabled": False,
                        "uri": ""
                    },
                    "scp": {
                        "enabled": True,
                        "uri": ""
                    }
                }
            },
            "upf": {
                "pfcp": [
                    {
                        "address": "10.180.3.74",
                        "dnn": "internet"
                    }
                ]
            },
            "pcrf": {
                "enabled": False,
                "frdi": {
                    "hostname": "",
                    "port": 3868
                }
            },
            "dnsList": [
                "8.8.8.8",
                "8.8.4.4",
                "2001:4860:4860::8888",
                "2001:4860:4860::8844"
            ],
            "subnetList": [
                {
                    "subnet": "10.45.0.0/16",
                    "gateway": "10.45.0.1",
                    "dnn": "internet"
                }
            ],
            "mtu": 1400,
            "info": [
                {
                    "s_nssai": [
                        {
                            "sst": 1,
                            "sd": "000001",
                            "dnn": [
                                "internet"
                            ]
                        }
                    ],
                    "tai": [
                        {
                            "plmn_id": {
                                "mcc": "001",
                                "mnc": "01"
                            },
                            "tac": 1
                        }
                    ]
                }
            ]
        },
        "multus": {
            "enabled": False,
            "n4network": {
                "enabled": False,
                "name": "n4network",
                "type": "macvlan",
                "masterIf": "eth0",
                "interfaceName": "n4",
                "ipAddress": "",
                "subnetMask": "",
                "gatewayIP": ""
            },
            "networkAttachments": []
        }
    },
    "upf": {
        "enabled": False
    },
    "webui": {
        "enabled": True
    },
    # "hss": {
    #     "enabled": False,
    #     "mongodb": {
    #         "enabled": False
    #     }
    # },
    # "mme": {
    #     "enabled": False
    # },
    # "pcrf": {
    #     "enabled": False,
    #     "mongodb": {
    #         "enabled": False
    #     }
    # },
    # "sgwc": {
    #     "enabled": False
    # },
    # "sgwu": {
    #     "enabled": False
    # },
    "amf": {
        "enabled": True,
        "config": {
            "ngap": {
                "dev": "eth0"
            },
            "logLevel": "debug",
            "sbi": {
                "client": {
                    "nrf": {
                        "enabled": False,
                        "uri": ""
                    },
                    "scp": {
                        "enabled": True,
                        "uri": ""
                    }
                }
            },
            "guamiList": [
                {
                    "plmn_id": {
                        "mcc": "001",
                        "mnc": "01"
                    },
                    "amf_id": {
                        "region": 2,
                        "set": 1
                    }
                }
            ],
            "taiList": [
                {
                    "plmn_id": {
                        "mcc": "001",
                        "mnc": "01"
                    },
                    "tac": [
                        1
                    ]
                }
            ],
            "plmnList": [
                {
                    "plmn_id": {
                        "mcc": "001",
                        "mnc": "01"
                    },
                    "s_nssai": [
                        {
                            "sst": 1,
                            "sd": "000001"
                        }
                    ]
                }
            ],
            "networkName": "Gradiant"
        },
        "multus": {
            "enabled": False,
            "n2network": {
                "enabled": False,
                "name": "n2network",
                "type": "macvlan",
                "masterIf": "eth0",
                "interfaceName": "n2",
                "ipAddress": "",
                "subnetMask": "",
                "gatewayIP": ""
            },
            "networkAttachments": []
        }
    },
    "ausf": {
        "enabled": True,
        "config": {
            "logLevel": "debug",
            "sbi": {
                "client": {
                    "nrf": {
                        "enabled": False,
                        "uri": ""
                    },
                    "scp": {
                        "enabled": True,
                        "uri": ""
                    }
                }
            }
        }
    },
    "bsf": {
        "enabled": True,
        "config": {
            "logLevel": "debug",
            "sbi": {
                "client": {
                    "nrf": {
                        "enabled": False,
                        "uri": ""
                    },
                    "scp": {
                        "enabled": True,
                        "uri": ""
                    }
                }
            }
        }
    },
    "nrf": {
        "enabled": True,
        "config": {
            "logLevel": "debug",
            "servingList": [
                {
                    "plmn_id": {
                        "mcc": "001",
                        "mnc": "01"
                    }
                }
            ]
        }
    },
    "nssf": {
        "enabled": True,
        "config": {
            "logLevel": "debug",
            "sbi": {
                "client": {
                    "nrf": {
                        "enabled": False,
                        "uri": ""
                    },
                    "scp": {
                        "enabled": True,
                        "uri": ""
                    }
                }
            },
            "nsiList": [
                {
                    "uri": "",
                    "sst": 1,
                    "sd": "000001"
                }
            ]
        }
    },
    "pcf": {
        "enabled": True,
        "mongodb": {
            "enabled": False
        },
        "config": {
            "logLevel": "debug",
            "sbi": {
                "client": {
                    "nrf": {
                        "enabled": False,
                        "uri": ""
                    },
                    "scp": {
                        "enabled": True,
                        "uri": ""
                    }
                }
            }
        }
    },
    "scp": {
        "enabled": True,
        "mongodb": {
            "enabled": False
        },
        "config": {
            "logLevel": "debug",
            "sbi": {
                "client": {
                    "nrf": {
                        "enabled": True,
                        "uri": ""
                    }
                }
            }
        }
    },
    "udm": {
        "enabled": True,
        "config": {
            "logLevel": "debug",
            "sbi": {
                "client": {
                    "nrf": {
                        "enabled": False,
                        "uri": ""
                    },
                    "scp": {
                        "enabled": True,
                        "uri": ""
                    }
                }
            }
        }
    },
    "udr": {
        "enabled": True,
        "config": {
            "logLevel": "debug",
            "sbi": {
                "client": {
                    "nrf": {
                        "enabled": False,
                        "uri": ""
                    },
                    "scp": {
                        "enabled": True,
                        "uri": ""
                    }
                }
            }
        }
    }
})
