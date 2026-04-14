from nfvcl_models.blueprint_ng.open5gs.upfK8s import Open5GsUpfK8sConfig

default_upf_config: Open5GsUpfK8sConfig = Open5GsUpfK8sConfig.model_validate({
    "config": {
        "logLevel": "debug",
        "upf": {
            "pfcp": {
                "address": "",
                "advertise": "",
                "nodeID": ""
            },
            "gtpu": {
                "address": "",
                "advertise": ""
            },
            "gnbSubnet": ""
        },
        "subnetList": [
            {
                "subnet": "10.45.0.0/16",
                "gateway": "10.45.0.1",
                "dnn": "internet",
                "dev": "ogstun",
                "mask": 16,
                "enableNAT": False
            }
        ]
    },
    "multus": {
        "enabled": True,
        "n3network": {
            "enabled": True,
            "name": "n3network",
            "type": "macvlan",
            "masterIf": "eth0",
            "interfaceName": "n3",
            "ipAddress": "",
            "subnetMask": "",
            "gatewayIP": ""
        },
        "n4network": {
            "enabled": True,
            "name": "n4network",
            "type": "macvlan",
            "masterIf": "eth1",
            "interfaceName": "n4",
            "ipAddress": "",
            "subnetMask": "",
            "gatewayIP": ""
        },
        "n6network": {
            "enabled": True,
            "name": "n6network",
            "type": "macvlan",
            "masterIf": "eth2",
            "interfaceName": "n6",
            "ipAddress": "",
            "subnetMask": "",
            "gatewayIP": ""
        },
        "networkAttachments": []
    }
})
