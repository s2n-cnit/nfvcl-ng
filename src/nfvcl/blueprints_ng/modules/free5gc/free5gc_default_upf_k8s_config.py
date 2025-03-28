from nfvcl_models.blueprint_ng.free5gc.free5gcUpfK8s import Free5gcK8sUpfConfig

default_upfk8s_config: Free5gcK8sUpfConfig = Free5gcK8sUpfConfig.model_validate({
    "global": {
        "projectName": "free5gc",
        "userPlaneArchitecture": "single",
        "uesubnet": ["10.1.0.0/16"],
        "n4network": {
            "enabled": True,
            "name": "n4network",
            "type": "macvlan",
            "masterIf": "eth0",
            "subnetIP": "10.100.50.240",
            "cidr": 29,
            "gatewayIP": "10.100.50.246",
            "excludeIP": "10.100.50.246"
        },
        "n3network": {
            "enabled": True,
            "name": "n3network",
            "type": "macvlan",
            "masterIf": "eth0",
            "subnetIP": "10.100.50.232",
            "cidr": 29,
            "gatewayIP": "10.100.50.238",
            "excludeIP": "10.100.50.238"
        },
        "n6network": {
            "enabled": False,
            "name": "n6network",
            "type": "macvlan",
            "masterIf": "eth1",
            "subnetIP": "10.100.100.0",
            "cidr": 24,
            "gatewayIP": "10.100.100.1",
            "excludeIP": "10.100.100.254"
        },
        "n9network": {
            "enabled": False,
            "name": "n9network",
            "type": "macvlan",
            "masterIf": "eth0",
            "subnetIP": "10.100.50.224",
            "cidr": 29,
            "gatewayIP": "10.100.50.230",
            "excludeIP": "10.100.50.230"
        }
    },
    "upf": {
        "name": "upf",
        "n3if": {
            "ipAddress": "10.100.50.233"
        },
        "n4if": {
            "ipAddress": "10.100.50.241"
        },
        "n6if": {
            "ipAddress": "127.0.0.1"
        },
        "configuration": {
            "dnnList": [
                {
                    "dnn": "internet",
                    "cidr": "10.1.0.0/17"
                }
            ],
            "logger": {
                "enable": True,
                "level": "debug",
                "reportCaller": False
            }
        }
    }
})
