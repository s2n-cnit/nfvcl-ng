from nfvcl_models.blueprint_ng.sdcore.sdcoreUpfK8s import SdcoreK8sUpfConfig

default_sdcore_upfk8s_config: SdcoreK8sUpfConfig = SdcoreK8sUpfConfig.model_validate(
    {
        "config": {
            "upf": {
                "privileged": True,
                "prometheus": {
                    "port": 8080
                },
                "hugepage": {
                    "enabled": False
                },
                "sriov": {
                    "enabled": False
                },
                "ipam": "static",
                "cniPlugin": "macvlan",
                "enb": {
                    "subnet": "192.168.251.0/24"
                },
                "access": {
                    "resourceName": "intel.com/intel_sriov_vfio",
                    "gateway": "10.163.0.1",
                    "ip": "10.163.255.38/16",
                    "iface": "ens8"
                },
                "core": {
                    "resourceName": "intel.com/intel_sriov_vfio",
                    "gateway": "10.164.0.1",
                    "ip": "10.164.255.39/16",
                    "iface": "ens9"
                },
                "n4": {
                    "resourceName": "intel.com/intel_sriov_vfio",
                    "gateway": "10.180.0.1",
                    "ip": "10.180.255.40/16",
                    "iface": "ens4"
                },
                "cfgFiles": {
                    "upf.jsonc": {
                        "mode": "af_packet",
                        "workers": 1,
                        "log_level": "info",
                        "hwcksum": False,
                        "gtppsc": False,
                        "ddp": False,
                        "max_req_retries": 5,
                        "resp_timeout": "2s",
                        "enable_ntf": False,
                        "enable_p4rt": False,
                        "enable_hbTimer": False,
                        "enable_gtpu_path_monitoring": False,
                        "p4rtciface": {
                            "access_ip": "172.17.0.1/32",
                            "p4rtc_server": "onos",
                            "p4rtc_port": "51001",
                            "slice_id": 0,
                            "default_tc": 3,
                            "clear_state_on_restart": False
                        },
                        "max_sessions": 50000,
                        "table_sizes": {
                            "pdrLookup": 50000,
                            "appQERLookup": 200000,
                            "sessionQERLookup": 100000,
                            "farLookup": 150000
                        },
                        "access": {
                            "ifname": "access"
                        },
                        "core": {
                            "ifname": "core"
                        },
                        "n4": {
                            "ifname": "n4"
                        },
                        "measure_upf": True,
                        "measure_flow": False,
                        "enable_notify_bess": True,
                        "notify_sockaddr": "/pod-share/notifycp",
                        "cpiface": {
                            "dnn": "internet",
                            "hostname": "upf",
                            "http_port": "8080",
                            "enable_ue_ip_alloc": False,
                            "ue_ip_pool": "10.250.0.0/16"
                        },
                        "slice_rate_limit_config": {
                            "n6_bps": 500000000,
                            "n6_burst_bytes": 625000,
                            "n3_bps": 500000000,
                            "n3_burst_bytes": 625000
                        },
                        "qci_qos_config": [
                            {
                                "qci": 0,
                                "cbs": 50000,
                                "ebs": 50000,
                                "pbs": 50000,
                                "burst_duration_ms": 10,
                                "priority": 7
                            },
                            {
                                "qci": 9,
                                "cbs": 2048,
                                "ebs": 2048,
                                "pbs": 2048,
                                "priority": 6
                            },
                            {
                                "qci": 8,
                                "cbs": 2048,
                                "ebs": 2048,
                                "pbs": 2048,
                                "priority": 5
                            }
                        ]
                    }
                }
            }
        }
    }
)
