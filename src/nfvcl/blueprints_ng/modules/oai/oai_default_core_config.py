from nfvcl.blueprints.blue_oai_cn5g.models.blue_OAI_model import OaiCoreValuesModel

# Class rappresenting default config, it will be overwritten with the input one
default_core_config: OaiCoreValuesModel = OaiCoreValuesModel.model_validate({
    "global": {
        "nfConfigurationConfigMap": "oai-5g-basic",
        "clusterIpServiceIpAllocation": True,
        "waitForNRF": True,
        "http2Param": "--http2-prior-knowledge",
        "timeout": 1
    },
    "mysql": {
        "enabled": True,
        "imagePullPolicy": "IfNotPresent",
        "oai5gdatabase": "basic",
        "service": {
            "annotations": {},
            "type": "LoadBalancer",
            "port": 3306
        },
        "imagePullSecrets": [
            {
                "name": "regcred"
            }
        ],
        "persistence": {
            "enabled": False
        }
    },
    "oai-nrf": {
        "enabled": True,
        "kubernetesType": "Vanilla",
        "nfimage": {
            "repository": "docker.io/oaisoftwarealliance/oai-nrf",
            "version": "v2.0.0",
            "pullPolicy": "IfNotPresent"
        },
        "includeTcpDumpContainer": False,
        "imagePullSecrets": [
            {
                "name": "regcred"
            }
        ],
        "config": {
            "logLevel": "debug"
        },
        "nodeSelector": {}
    },
    "oai-udr": {
        "enabled": True,
        "kubernetesType": "Vanilla",
        "nfimage": {
            "repository": "docker.io/oaisoftwarealliance/oai-udr",
            "version": "v2.0.0",
            "pullPolicy": "IfNotPresent"
        },
        "includeTcpDumpContainer": False,
        "imagePullSecrets": [
            {
                "name": "regcred"
            }
        ],
        "config": {
            "logLevel": "debug"
        },
        "nodeSelector": {}
    },
    "oai-udm": {
        "enabled": True,
        "kubernetesType": "Vanilla",
        "nfimage": {
            "repository": "docker.io/oaisoftwarealliance/oai-udm",
            "version": "v2.0.0",
            "pullPolicy": "IfNotPresent"
        },
        "includeTcpDumpContainer": False,
        "imagePullSecrets": [
            {
                "name": "regcred"
            }
        ],
        "config": {
            "logLevel": "debug"
        },
        "nodeSelector": {}
    },
    "oai-ausf": {
        "enabled": True,
        "kubernetesType": "Vanilla",
        "nfimage": {
            "repository": "docker.io/oaisoftwarealliance/oai-ausf",
            "version": "v2.0.0",
            "pullPolicy": "IfNotPresent"
        },
        "includeTcpDumpContainer": False,
        "imagePullSecrets": [
            {
                "name": "regcred"
            }
        ],
        "config": {
            "logLevel": "debug"
        },
        "nodeSelector": {}
    },
    "oai-amf": {
        "enabled": True,
        "kubernetesType": "Vanilla",
        "nfimage": {
            "repository": "docker.io/oaisoftwarealliance/oai-amf",
            "version": "v2.0.0",
            "pullPolicy": "IfNotPresent"
        },
        "includeTcpDumpContainer": False,
        "imagePullSecrets": [
            {
                "name": "regcred"
            }
        ],
        "multus": {
            "defaultGateway": "",
            "n2Interface": {
                "create": False,
                "Ipadd": "172.21.6.94",
                "Netmask": "22",
                "Gateway": None,
                "routes": [
                    {
                        "dst": "10.8.0.0/24",
                        "gw": "172.21.7.254"
                    }
                ],
                "hostInterface": "bond0"
            }
        },
        "nodeSelector": {}
    },
    "oai-smf": {
        "enabled": True,
        "kubernetesType": "Vanilla",
        "nfimage": {
            "repository": "docker.io/oaisoftwarealliance/oai-smf",
            "version": "v2.0.0",
            "pullPolicy": "IfNotPresent"
        },
        "includeTcpDumpContainer": False,
        "hostAliases": [
            {
                "ip": "10.180.2.41",
                "hostnames": "oai-upf"
            }
        ],
        "multus": {
            "defaultGateway": "",
            "n4Interface": {
                "create": False,
                "Ipadd": "192.168.24.3",
                "Netmask": "24",
                "Gateway": "",
                "hostInterface": "bond0"
            }
        },
        "imagePullSecrets": [
            {
                "name": "regcred"
            }
        ],
        "nodeSelector": {}
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
        "amf": {
            "amf_name": "OAI-AMF",
            "support_features_options": {
                "enable_simple_scenario": "no",
                "enable_nssf": "no",
                "enable_smf_selection": "yes"
            },
            "relative_capacity": 30,
            "statistics_timer_interval": 20,
            "emergency_support": False,
            "served_guami_list": [
                {
                    "mcc": "001",
                    "mnc": "01",
                    "amf_region_id": "01",
                    "amf_set_id": "001",
                    "amf_pointer": "01"
                }
            ],
            "plmn_support_list": [
                {
                    "mcc": "001",
                    "mnc": "01",
                    "tac": "1",
                    "nssai": [
                        {
                            "sst": 1
                        },
                        {
                            "sst": 1,
                            "sd": "FFFFFF"
                        }
                    ]
                }
            ],
            "supported_integrity_algorithms": [
                "NIA1",
                "NIA2"
            ],
            "supported_encryption_algorithms": [
                "NEA0",
                "NEA1",
                "NEA2"
            ]
        },
        "smf": {
            "ue_mtu": 1500,
            "support_features": {
                "use_local_subscription_info": "no",
                "use_local_pcc_rules": "yes"
            },
            "upfs": [
                {
                    "host": "oai-upf",
                    "config": {
                        "enable_usage_reporting": "no"
                    }
                }
            ],
            "ue_dns": {
                "primary_ipv4": "10.3.2.200",
                "primary_ipv6": "2001:4860:4860::8888",
                "secondary_ipv4": "8.8.8.8",
                "secondary_ipv6": "2001:4860:4860::8888"
            },
            "ims": {
                "pcscf_ipv4": "192.168.70.139",
                "pcscf_ipv6": "fe80::7915:f408:1787:db8b"
            },
            "smf_info": {
                "sNssaiSmfInfoList": [
                    {
                        "sNssai": {
                            "sst": 1
                        },
                        "dnnSmfInfoList": [
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
                        "dnnSmfInfoList": [
                            {
                                "dnn": "ims"
                            }
                        ]
                    }
                ]
            },
            "local_subscription_infos": [
                {
                    "single_nssai": {
                        "sst": 1
                    },
                    "dnn": "oai",
                    "qos_profile": {
                        "5qi": 5,
                        "session_ambr_ul": "200Mbps",
                        "session_ambr_dl": "400Mbps"
                    }
                },
                {
                    "single_nssai": {
                        "sst": 1,
                        "sd": "FFFFFF"
                    },
                    "dnn": "ims",
                    "qos_profile": {
                        "5qi": 2,
                        "session_ambr_ul": "100Mbps",
                        "session_ambr_dl": "200Mbps"
                    }
                }
            ]
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
