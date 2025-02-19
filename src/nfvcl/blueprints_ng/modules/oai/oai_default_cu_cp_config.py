from nfvcl_models.blueprint_ng.core5g.OAI_Models import CUCP

default_cucp_config: CUCP = CUCP.model_validate({
    "multus": {
        "defaultGateway": "",
        "e1Interface": {
            "create": False,
            "ipAdd": "192.168.18.12",
            "netmask": "24",
            "mac": "",
            "name": "e1",
            "gateway": "",
            "routes": [],
            "hostInterface": "bond0"
        },
        "n2Interface": {
            "create": False,
            "ipAdd": "172.21.8.97",
            "name": "n2",
            "netmask": "22",
            "mac": "",
            "gateway": "",
            "routes": [],
            "hostInterface": "bond0"
        },
        "f1cInterface": {
            "create": False,
            "ipAdd": "172.21.16.92",
            "netmask": "22",
            "mac": "",
            "name": "f1c",
            "gateway": "172.21.19.254",
            "routes": [],
            "hostInterface": "bond0"
        }
    },
    "config": {
        "timeZone": "Europe/Paris",
        "useAdditionalOptions": "--sa --log_config.global_log_options level,nocolor,time",
        "cucpName": "oai-cu-cp",
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
        "f1IfName": "eth0",
        "e1IfName": "eth0",
        "f1cuPort": "2153",
        "f1duPort": "2153"
    }
})
