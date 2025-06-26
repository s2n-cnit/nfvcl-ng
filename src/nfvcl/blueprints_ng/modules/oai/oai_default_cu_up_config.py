from nfvcl_models.blueprint_ng.core5g.OAI_Models import CUUP

default_cuup_config: CUUP = CUUP.model_validate({
    "multus": {
        "defaultGateway": "",
        "e1Interface": {
            "create": False,
            "ipAdd": "192.168.18.13",
            "netmask": "24",
            "mac": "",
            "name": "e1",
            "gateway": "",
            "routes": [],
            "hostInterface": "bond0"
        },
        "n3Interface": {
            "create": False,
            "name": "n3",
            "ipAdd": "172.29.4.17",
            "netmask": "24",
            "mac": "",
            "gateway": "",
            "routes": None,
            "hostInterface": "bond0"
        },
        "f1uInterface": {
            "create": False,
            "ipAdd": "172.21.16.93",
            "netmask": "24",
            "mac": "",
            "name": "f1u",
            "gateway": "172.21.19.254",
            "routes": None,
            "hostInterface": "bond0"
        }
    },
    "config": {
        "timeZone": "Europe/Paris",
        "useAdditionalOptions": "--sa",
        "cuupName": "oai-cuup",
        "mcc": "001",
        "mnc": "01",
        "tac": "1",
        "snssaiList": [
            {
                "sst": 1,
                "sd": "000001"
            }
        ],
        "flexrichost": "",
        "cuCpHost": "172.29.4.13",
        "n2IfName": "eth0",
        "n3IfName": "eth0",
        "f1IfName": "eth0",
        "e1IfName": "eth0",
        "f1cuPort": "2153",
        "f1duPort": "2153",
        "additional_routes": []
    }
})
