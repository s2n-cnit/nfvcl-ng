from utils import get_unittest_config

unittest_config = get_unittest_config()

K8S_CLUSTER_5G = {
    "cni": "flannel",
    "pod_network_cidr": "10.254.0.0/16",
    "topology_onboard": True,
    "require_port_security_disabled": True,
    "master_flavors": {
        "memory_mb": "8192",
        "storage_gb": "32",
        "vcpu_count": "8"
    },
    "areas": [
        {
            "area_id": 1,
            "is_master_area": True,
            "mgmt_net": "dmz-internal",
            "additional_networks": [f"{unittest_config.config.networks.data.name}"],
            "load_balancer_pools_ips": unittest_config.config.networks.k8s_lb_ips,
            "worker_replicas": 1,
            "worker_flavors": {
                "memory_mb": "8192",
                "storage_gb": "32",
                "vcpu_count": "6"
            }
        }
    ]
}

UERANSIM1 = {
    "config": {
        "network_endpoints": {
            "mgt": f"{unittest_config.config.networks.mgmt.name}",
            "n2": f"{unittest_config.config.networks.data.name}",
            "n3": f"{unittest_config.config.networks.gnb.name}"
        }
    },
    "areas": [
        {
            "id": 1,
            "nci": "0x00000005",
            "idLength": 0,
            "ues": [
                {
                    "id": 1,
                    "sims": [
                        {
                            "imsi": "001014000000001",
                            "plmn": "00101",
                            "key": "814BCB2AEBDA557AEEF021BB21BEFE25",
                            "op": "9B5DA0D4EC1E2D091A6B47E3B91D2496",
                            "opType": "OPC",
                            "amf": "8000",
                            "configured_nssai": [
                                {
                                    "sst": 1,
                                    "sd": 1
                                }
                            ],
                            "default_nssai": [
                                {
                                    "sst": 1,
                                    "sd": 1
                                }
                            ],
                            "sessions": [
                                {
                                    "type": "IPv4",
                                    "apn": "dnn",
                                    "slice": {
                                        "sst": 1,
                                        "sd": 1
                                    }
                                }
                            ]
                        },
                        {
                            "imsi": "001014000000002",
                            "plmn": "00101",
                            "key": "814BCB2AEBDA557AEEF021BB21BEFE25",
                            "op": "9B5DA0D4EC1E2D091A6B47E3B91D2496",
                            "opType": "OPC",
                            "amf": "8000",
                            "configured_nssai": [
                                {
                                    "sst": 1,
                                    "sd": 1
                                }
                            ],
                            "default_nssai": [
                                {
                                    "sst": 1,
                                    "sd": 1
                                }
                            ],
                            "sessions": [
                                {
                                    "type": "IPv4",
                                    "apn": "dnn",
                                    "slice": {
                                        "sst": 1,
                                        "sd": 1
                                    }
                                }
                            ]
                        }
                    ]
                }
            ]
        }
    ]
}

UERANSIM2 = {
    "config": {
        "network_endpoints": {
            "mgt": f"{unittest_config.config.networks.mgmt.name}",
            "n2": f"{unittest_config.config.networks.data.name}",
            "n3": f"{unittest_config.config.networks.gnb.name}"
        }
    },
    "areas": [
        {
            "id": 2,
            "nci": "0x00000005",
            "idLength": 0,
            "ues": [
                {
                    "id": 1,
                    "sims": [
                        {
                            "imsi": "001014000000003",
                            "plmn": "00101",
                            "key": "814BCB2AEBDA557AEEF021BB21BEFE25",
                            "op": "9B5DA0D4EC1E2D091A6B47E3B91D2496",
                            "opType": "OPC",
                            "amf": "8000",
                            "configured_nssai": [
                                {
                                    "sst": 1,
                                    "sd": 1
                                }
                            ],
                            "default_nssai": [
                                {
                                    "sst": 1,
                                    "sd": 1
                                }
                            ],
                            "sessions": [
                                {
                                    "type": "IPv4",
                                    "apn": "dnn",
                                    "slice": {
                                        "sst": 1,
                                        "sd": 1
                                    }
                                }
                            ]
                        }
                    ]
                }
            ]
        }
    ]
}

CORE_5G = {
    "config": {
        "network_endpoints": {
            "mgt": unittest_config.config.networks.mgmt.name,
            "n2": unittest_config.config.networks.data.name,
            "n4": unittest_config.config.networks.data.name,
            "data_nets": [
                {
                    "net_name": "dnn",
                    "dnn": "dnn",
                    "dns": "8.8.8.8",
                    "pools": [
                        {
                            "cidr": "12.168.0.0/16"
                        }
                    ],
                    "uplinkAmbr": "100 Mbps",
                    "downlinkAmbr": "100 Mbps",
                    "default5qi": "9"
                }
            ]
        },
        "plmn": "00101",
        "sliceProfiles": [
            {
                "sliceId": "000001",
                "sliceType": "EMBB",
                "dnnList": ["dnn"],
                "profileParams": {
                    "isolationLevel": "ISOLATION",
                    "sliceAmbr": "1000 Mbps",
                    "ueAmbr": "50 Mbps",
                    "maximumNumberUE": 10,
                    "pduSessions": [
                        {
                            "pduSessionId": "1",
                            "pduSessionAmbr": "20 Mbps",
                            "flows": [{
                                "flowId": "1",
                                "ipAddrFilter": "8.8.4.4",
                                "qi": "9",
                                "gfbr": "10 Mbps"
                            }]
                        }
                    ]
                },
                "locationConstraints": [
                    {
                        "geographicalAreaId": "1",
                        "tai": "00101000001"
                    }
                ],
                "enabledUEList": [
                    {
                        "ICCID": "*"
                    }
                ]
            }
        ],
        "subscribers": [
            {
                "imsi": "001014000000001",
                "k": "814BCB2AEBDA557AEEF021BB21BEFE25",
                "opc": "9B5DA0D4EC1E2D091A6B47E3B91D2496",
                "snssai": [
                    {
                        "sliceId": "000001",
                        "sliceType": "EMBB",
                        "pduSessionIds": [
                            "1"
                        ],
                        "default_slice": True
                    }
                ],
                "authenticationMethod": "5G_AKA",
                "authenticationManagementField": "8000"
            }
        ]
    },
    "areas": [
        {
            "id": 1,
            "nci": "0x0",
            "idLength": 32,
            "core": True,
            "networks": {
                "n3": unittest_config.config.networks.n3.name,
                "n6": unittest_config.config.networks.n6.name,
                "gnb": unittest_config.config.networks.gnb.name
            },
            "slices": [{
                "sliceType": "EMBB",
                "sliceId": "000001"
            }]
        }
    ]
}
