from blueprints_ng.modules.sdcore.sdcore_values_model import SDCoreValuesModel

default_config: SDCoreValuesModel = SDCoreValuesModel.model_validate({
    "5g-control-plane": {
        "enable5G": True,
        "images": {
            "repository": "registry.opennetworking.org/docker.io/"
        },
        "kafka": {
            "deploy": True
        },
        "mongodb": {
            "readinessProbe": {
                "timeoutSeconds": 20
            },
            "livenessProbe": {
                "timeoutSeconds": 20
            },
            "usePassword": False,
            "persistence": {
                "enabled": False
            },
            "architecture": "replicaset",
            "replicaCount": 2
        },
        "resources": {
            "enabled": False
        },
        "config": {
            "mongodb": {
                "name": "free5gc",
                "url": "mongodb://mongodb-arbiter-headless"
            },
            "managedByConfigPod": {
                "enabled": True
            },
            "sctplb": {
                "deploy": False
            },
            "upfadapter": {
                "deploy": False
            },
            "metricfunc": {
                "deploy": True,
                "serviceType": "LoadBalancer"
            },
            "webui": {
                "serviceType": "LoadBalancer"
            },
            "amf": {
                "serviceType": "LoadBalancer",
                "cfgFiles": {
                    "amfcfg.conf": {
                        "configuration": {
                            "enableDBStore": False
                        }
                    }
                }
            },
            "smf": {
                "serviceType": "LoadBalancer",
                "cfgFiles": {
                    "smfcfg.conf": {
                        "configuration": {
                            "enableDBStore": False
                        }
                    }
                }
            },
            "nrf": {
                "serviceType": "LoadBalancer",
                "cfgFiles": {
                    "nrfcfg.conf": {
                        "configuration": {
                            "mongoDBStreamEnable": False,
                            "nfProfileExpiryEnable": False,
                            "nfKeepAliveTime": 60
                        }
                    }
                }
            }
        }
    },
    "omec-sub-provision": {
        "enable": True,
        "images": {
            "repository": "registry.opennetworking.org/docker.io/"
        },
        "config": {
            "simapp": {
                "cfgFiles": {
                    "simapp.yaml": {
                        "info": {
                            "version": "1.0.0"
                        },
                        "configuration": {
                            "provision-network-slice": True,
                            "sub-provision-endpt": {
                                "addr": "webui"
                            },
                            "subscribers": [
                                {
                                    "ueId-start": "208930100007487",
                                    "ueId-end": "208930100007500",
                                    "plmnId": "20893",
                                    "opc": "981d464c7c52eb6e5036234984ad0bcf",
                                    "op": "",
                                    "key": "5122250214c33e723a5dd523fc145fc0",
                                    "sequenceNumber": "16f3b3f70fc2"
                                }
                            ],
                            "device-groups": [
                                {
                                    "name": "5g-gnbsim-user-group1",
                                    "imsis": [
                                        "208930100007487",
                                    ],
                                    "ip-domain-name": "pool1",
                                    "ip-domain-expanded": {
                                        "dnn": "internet",
                                        "dns-primary": "8.8.8.8",
                                        "mtu": 1410,
                                        "ue-ip-pool": "172.250.1.0/16",
                                        "ue-dnn-qos": {
                                            "dnn-mbr-downlink": 100,
                                            "dnn-mbr-uplink": 100,
                                            "bitrate-unit": "gbps",
                                            "traffic-class": {
                                                "name": "platinum",
                                                "qci": 9,
                                                "arp": 6,
                                                "pdb": 300,
                                                "pelr": 6
                                            }
                                        }
                                    },
                                    "site-info": "aiab"
                                },
                                {
                                    "name": "5g-gnbsim-user-group2",
                                    "imsis": [
                                        "208930100007488"
                                    ],
                                    "ip-domain-name": "pool1",
                                    "ip-domain-expanded": {
                                        "dnn": "internet",
                                        "dns-primary": "8.8.8.8",
                                        "mtu": 1410,
                                        "ue-ip-pool": "172.250.1.0/16",
                                        "ue-dnn-qos": {
                                            "dnn-mbr-downlink": 100,
                                            "dnn-mbr-uplink": 100,
                                            "bitrate-unit": "gbps",
                                            "traffic-class": {
                                                "name": "platinum",
                                                "qci": 9,
                                                "arp": 6,
                                                "pdb": 300,
                                                "pelr": 6
                                            }
                                        }
                                    },
                                    "site-info": "aiab2"
                                }
                            ],
                            "network-slices": [
                                {
                                    "name": "default",
                                    "slice-id": {
                                        "sd": "010203",
                                        "sst": 1
                                    },
                                    "site-device-group": [
                                        "5g-gnbsim-user-group1",
                                    ],
                                    "application-filtering-rules": [
                                        {
                                            "rule-name": "ALLOW-ALL",
                                            "priority": 250,
                                            "action": "permit",
                                            "endpoint": "0.0.0.0/0"
                                        }
                                    ],
                                    "site-info": {
                                        "gNodeBs": [
                                            {
                                                "name": "aiab-gnb1",
                                                "tac": 1
                                            },
                                            {
                                                "name": "aiab-gnb2",
                                                "tac": 2
                                            }
                                        ],
                                        "plmn": {
                                            "mcc": "208",
                                            "mnc": "93"
                                        },
                                        "site-name": "aiab",
                                        "upf": {
                                            "upf-name": "upf",
                                            "upf-port": 8805
                                        }
                                    }
                                },
                                {
                                    "name": "slice2",
                                    "slice-id": {
                                        "sd": "010204",
                                        "sst": 1
                                    },
                                    "site-device-group": [
                                        "5g-gnbsim-user-group2",
                                    ],
                                    "application-filtering-rules": [
                                        {
                                            "rule-name": "ALLOW-ALL",
                                            "priority": 250,
                                            "action": "permit",
                                            "endpoint": "0.0.0.0/0"
                                        }
                                    ],
                                    "site-info": {
                                        "gNodeBs": [
                                            {
                                                "name": "aiab-gnb1",
                                                "tac": 1
                                            },
                                            {
                                                "name": "aiab-gnb2",
                                                "tac": 2
                                            }
                                        ],
                                        "plmn": {
                                            "mcc": "208",
                                            "mnc": "93"
                                        },
                                        "site-name": "aiab2",
                                        "upf": {
                                            "upf-name": "upf",
                                            "upf-port": 8805
                                        }
                                    }
                                }
                            ]
                        }
                    }
                }
            }
        }
    },
    "omec-control-plane": {
        "enable4G": False
    },
    "omec-user-plane": {
        "enable": False,
    },
    "5g-ran-sim": {
        "enable": False,
    }
})
