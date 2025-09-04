from nfvcl_models.blueprint_ng.core5g.OAI_Models import OaiUpfValuesModel

# Class representing default config, it will be overwritten with the input one
default_upf_config: OaiUpfValuesModel = OaiUpfValuesModel.model_validate({
    "multus": {
        "defaultGateway": "",
        "n3Interface": {
            "create": False,
            "ipAdd": "172.21.12.95",
            "netmask": "22",
            "name": "n3",
            "routes": [],
            "hostInterface": "bond0"
        },
        "n4Interface": {
            "create": False,
            "ipAdd": "192.168.24.2",
            "netmask": "24",
            "name": "n4",
            "routes": [],
            "hostInterface": "bond0"
        },
        "n6Interface": {
            "create": False,
            "ipAdd": "192.168.22.2",
            "netmask": "24",
            "name": "n6",
            "routes": [],
            "hostInterface": "bond0"
        }
    },
    "currentconfig": {
        "log_level": {
            "general": "info"
        },
        "register_nf": {
            "general": "yes"
        },
        "http_version": 2,
        "snssais": [
            {
                "sst": 1,
                "sd": "FFFFFF"
            }
        ],
        "nfs": {
            "amf": {
                "host": "oai-amf",
                "sbi": {
                    "port": 80,
                    "api_version": "v1",
                    "interface_name": "eth0"
                },
                "n2": {
                    "interface_name": "eth0",
                    "port": 38412
                }
            },
            "smf": {
                "host": "oai-smf",
                "sbi": {
                    "port": 80,
                    "api_version": "v1",
                    "interface_name": "eth0"
                },
                "n4": {
                    "interface_name": "eth0",
                    "port": 8805
                }
            },
            "upf": {
                "host": "oai-upf",
                "sbi": {
                    "port": 80,
                    "api_version": "v1",
                    "interface_name": "eth0"
                },
                "n3": {
                    "interface_name": "eth0",
                    "port": 2152
                },
                "n4": {
                    "interface_name": "eth0",
                    "port": 8805
                },
                "n6": {
                    "interface_name": "eth0"
                },
                "n9": {
                    "interface_name": "eth0",
                    "port": 2152
                }
            },
            "udm": {
                "host": "oai-udm",
                "sbi": {
                    "port": 80,
                    "api_version": "v1",
                    "interface_name": "eth0"
                }
            },
            "udr": {
                "host": "oai-udr",
                "sbi": {
                    "port": 80,
                    "api_version": "v1",
                    "interface_name": "eth0"
                }
            },
            "ausf": {
                "host": "oai-ausf",
                "sbi": {
                    "port": 80,
                    "api_version": "v1",
                    "interface_name": "eth0"
                }
            },
            "nrf": {
                "host": "oai-nrf",
                "sbi": {
                    "port": 80,
                    "api_version": "v1",
                    "interface_name": "eth0"
                }
            }
        },
        "database": {
            "host": "mysql",
            "user": "test",
            "type": "mysql",
            "password": "test",
            "database_name": "oai_db",
            "generate_random": True,
            "connection_timeout": 300
        },
        "upf": {
            "gnb_cidr": "10.1.128.0/17",
            "support_features": {
                "enable_bpf_datapath": "no",
                "enable_snat": "yes",
                "enable_qos": "no"
            },
            "remote_n6_gw": "localhost",
            "smfs": [
                {
                    "host": ""
                }
            ],
            "upf_info": {
                "sNssaiUpfInfoList": [
                    {
                        "sNssai": {
                            "sst": 1,
                            "sd": "FFFFFF"
                        },
                        "dnnUpfInfoList": [
                            {
                                "dnn": "oai"
                            }
                        ]
                    },
                    {
                        "sNssai": {
                            "sst": 1,
                            "sd": "FFFFFF"
                        },
                        "dnnUpfInfoList": [
                            {
                                "dnn": "ims"
                            }
                        ]
                    }
                ]
            }
        },
        "dnns": [
            {
                "dnn": "oai",
                "pdu_session_type": "IPV4",
                "ipv4_subnet": "10.1.0.0/24"
            },
            {
                "dnn": "ims",
                "pdu_session_type": "IPV4V6",
                "ipv4_subnet": "10.2.0.0/24"
            }
        ]
    }
})
