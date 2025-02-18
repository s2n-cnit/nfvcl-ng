from nfvcl_models.blueprint_ng.core5g.OAI_Models import OaiCoreValuesModel

# Class rappresenting default config, it will be overwritten with the input one
default_core_config: OaiCoreValuesModel = OaiCoreValuesModel.model_validate({
    "global": {
        "kubernetesDistribution": "Vanilla",
        "coreNetworkConfigMap": "oai-5g-basic",
        "clusterIpServiceIpAllocation": True,
        "waitForNRF": True,
        "waitForUDR": True,
        "http2Param": "--http2-prior-knowledge",
        "timeout": 1
    },
    "mysql": {
        "enabled": True,
        "imagePullPolicy": "IfNotPresent",
        "oai5gdatabase": "basic",
        "imagePullSecrets": [
            {
                "name": "regcred"
            }
        ],
        "persistence": {
            "enabled": True,
            "storageClass": ""
        }
    },
    "oai-nrf": {
        "enabled": True,
        "nfimage": {
            "repository": "docker.io/oaisoftwarealliance/oai-nrf",
            "version": "v2.1.0",
            "pullPolicy": "IfNotPresent"
        },
        "includeTcpDumpContainer": False,
        "persistent": {
            "sharedvolume": False,
            "storageClass": "-",
            "size": "1Gi"
        },
        "start": {
            "nrf": True,
            "tcpdump": False
        },
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
    "oai-lmf": {
        "enabled": True,
        "nfimage": {
            "repository": "docker.io/oaisoftwarealliance/oai-lmf",
            "version": "v2.1.0",
            "pullPolicy": "IfNotPresent"
        },
        "includeTcpDumpContainer": False,
        "persistent": {
            "sharedvolume": False
        },
        "start": {
            "lmf": True,
            "tcpdump": False
        },
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
        "nfimage": {
            "repository": "docker.io/oaisoftwarealliance/oai-udr",
            "version": "v2.1.0",
            "pullPolicy": "IfNotPresent"
        },
        "includeTcpDumpContainer": False,
        "persistent": {
            "sharedvolume": False
        },
        "start": {
            "udr": True,
            "tcpdump": False
        },
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
        "nfimage": {
            "repository": "docker.io/oaisoftwarealliance/oai-udm",
            "version": "v2.1.0",
            "pullPolicy": "IfNotPresent"
        },
        "includeTcpDumpContainer": False,
        "persistent": {
            "sharedvolume": False
        },
        "start": {
            "udm": True,
            "tcpdump": False
        },
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
        "nfimage": {
            "repository": "docker.io/oaisoftwarealliance/oai-ausf",
            "version": "v2.1.0",
            "pullPolicy": "IfNotPresent"
        },
        "includeTcpDumpContainer": False,
        "persistent": {
            "sharedvolume": False
        },
        "start": {
            "ausf": True,
            "tcpdump": False
        },
        "imagePullSecrets": [
            {
                "name": "regcred"
            }
        ],
        "securityContext": {
            "privileged": False
        },
        "config": {
            "logLevel": "debug"
        },
        "nodeSelector": {}
    },
    "oai-amf": {
        "enabled": True,
        "nfimage": {
            "repository": "docker.io/oaisoftwarealliance/oai-amf",
            "version": "v2.0.0",
            "pullPolicy": "IfNotPresent"
        },
        "includeTcpDumpContainer": False,
        "persistent": {
            "sharedvolume": False
        },
        "multus": {
            "defaultGateway": "",
            "n2Interface": {
                "create": False,
                "ipAdd": "192.168.24.2",
                "netmask": "24",
                "name": "n2",
                "mac": "",
                "routes": [],
                "hostInterface": "bond0"
            }
        },
        "start": {
            "amf": True,
            "tcpdump": False
        },
        "imagePullSecrets": [
            {
                "name": "regcred"
            }
        ],
        "securityContext": {
            "privileged": False
        },
        "config": {
            "logLevel": "debug"
        },
        "nodeSelector": {}
    },
    "oai-smf": {
        "enabled": True,
        "nfimage": {
            "repository": "docker.io/oaisoftwarealliance/oai-smf",
            "version": "v2.1.0",
            "pullPolicy": "IfNotPresent"
        },
        "includeTcpDumpContainer": False,
        "persistent": {
            "sharedvolume": False
        },
        "start": {
            "smf": True,
            "tcpdump": False
        },
        "multus": {
            "defaultGateway": "",
            "n4Interface": {
                "create": False,
                "ipAdd": "192.168.24.2",
                "netmask": "24",
                "name": "n4",
                "mac": "",
                "routes": [],
                "hostInterface": "bond0"
            }
        },
        "config": {
            "logLevel": "debug"
        },
        "nodeSelector": {},
        "imagePullSecrets": [
            {
                "name": "regcred"
            }
        ]
    },
    "currentconfig": {
        "log_level": {
            "general": "debug"
        },
        "register_nf": {
            "general": "yes"
        },
        "http_version": 2,
        "curl_timeout": 6000,
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
            "lmf": {
                "host": "oai-lmf",
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
                "primary_ipv4": "8.8.8.8",
                "primary_ipv6": "2001:4860:4860::8888",
                "secondary_ipv4": "1.1.1.1",
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
                        "sst": 1,
                        "sd": "FFFFFF"
                    },
                    "dnn": "oai",
                    "qos_profile": {
                        "5qi": 6,
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
                        "5qi": 5,
                        "session_ambr_ul": "100Mbps",
                        "session_ambr_dl": "200Mbps"
                    }
                }
            ]
        },
        "lmf": {
            "http_threads_count": 8,
            "gnb_id_bits_count": 28,
            "num_gnb": 1,
            "trp_info_wait_ms": 10000,
            "positioning_wait_ms": 10000,
            "measurement_wait_ms": 10000,
            "support_features": {
                "request_trp_info": "no",
                "determine_num_gnb": "no",
                "use_http2": "yes",
                "use_fqdn_dns": "no",
                "register_nrf": "yes"
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
