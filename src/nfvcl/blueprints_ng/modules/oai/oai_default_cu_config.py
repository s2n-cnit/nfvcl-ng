from nfvcl_models.blueprint_ng.core5g.OAI_Models import CU

default_cu_config: CU = CU.model_validate({
    "multus": {
        "defaultGateway": "",
        "f1Interface": {
            "create": False,
            "ipAdd": "172.21.16.92",
            "netmask": "22",
            "mac": "",
            "name": "f1",
            "gateway": "",
            "routes": None,
            "hostInterface": "bond0"
        },
        "n2Interface": {
            "create": False,
            "ipAdd": "172.21.6.90",
            "name": "n2",
            "netmask": "22",
            "mac": "",
            "gateway": "",
            "routes": [],
            "hostInterface": "bond0"
        },
        "n3Interface": {
            "create": False,
            "ipAdd": "172.21.8.91",
            "name": "n3",
            "netmask": "22",
            "mac": "",
            "gateway": "",
            "routes": None,
            "hostInterface": "bond0"
        }
    },
    "config": {
        "timeZone": "Europe/Paris",
        "useAdditionalOptions": "--sa --log_config.global_log_options level,nocolor,time",
        "cuName": "oai-cu",
        "mcc": "001",
        "mnc": "01",
        "tac": "1",
        "snssaiList": [
            {
                "sst": 1,
                "sd": "000001"
            }
        ],
        "amfhost": "127.0.0.1",
        "n2IfName": "eth0",
        "n3IfName": "eth0",
        "f1IfName": "eth0",
        "f1cuPort": "2153",
        "f1duPort": "2153",
        "gnbId": "0xe00",
        "additional_routes": []
    }
})
