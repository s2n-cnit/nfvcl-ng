from nfvcl.blueprints.blue_oai_cn5g.models.blue_OAI_model import OaiUpfValuesModel

# Class rappresenting default config, it will be overwritten with the input one
default_upf_config: OaiUpfValuesModel = OaiUpfValuesModel.model_validate({
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
                "sst": 1
            },
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
            "support_features": {
                "enable_bpf_datapath": "no",
                "enable_snat": "yes"
            },
            "remote_n6_gw": "127.0.0.1",
            "upf_info": {
                "sNssaiUpfInfoList": [
                    {
                        "sNssai": {
                            "sst": 1
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
                "ipv4_subnet": "12.1.1.0/24"
            },
            {
                "dnn": "ims",
                "pdu_session_type": "IPV4V6",
                "ipv4_subnet": "14.1.1.0/24"
            }
        ]
    }
})
