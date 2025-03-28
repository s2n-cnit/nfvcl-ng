from nfvcl_models.blueprint_ng.core5g.OAI_Models import DU

default_du_config: DU = DU.model_validate({
    "multus": {
        "defaultGateway": "",
        "f1Interface": {
            "create": False,
            "ipAdd": "172.21.16.100",
            "netmask": "22",
            "mac": "",
            "name": "f1",
            "gateway": "",
            "routes": [],
            "hostInterface": "bond0"
        },
        "ru1Interface": {
            "create": False,
            "ipAdd": "172.21.16.100",
            "name": "ru1",
            "netmask": "22",
            "mac": "",
            "gateway": "",
            "hostInterface": "bond0"
        },
        "ru2Interface": {
            "create": False,
            "ipAdd": "172.21.16.102",
            "name": "ru2",
            "netmask": "22",
            "mac": "",
            "gateway": "",
            "hostInterface": "bond0"
        }
    },
    "config": {
        "timeZone": "Europe/Paris",
        "useAdditionalOptions": "--sa --rfsim --log_config.global_log_options level,nocolor,time",
        "duName": "oai-du-rfsim",
        "mcc": "001",
        "mnc": "01",
        "tac": "1",
        "snssaiList": [
            {
                "sst": 1,
                "sd": "000001"
            }
        ],
        "usrp": "rfsim",
        "f1IfName": "eth0",
        "cuHost": "oai-cu",
        "f1cuPort": "2153",
        "f1duPort": "2153",
        "gnbId": "0xe00"
    }
})
