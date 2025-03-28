from nfvcl_models.blueprint_ng.free5gc.free5gcUpf import Free5gcUpfConfig

default_upf_config: Free5gcUpfConfig = Free5gcUpfConfig.model_validate({
    "version": "1.0.3",
    "description": "UPF initial local configuration",
    "pfcp": {
        "addr": "10.180.1.252",
        "nodeID": "10.180.1.252",
        "retransTimeout": "1s",
        "maxRetrans": 3
    },
    "gtpu": {
        "forwarder": "gtp5g",
        "ifList": [
            {
                "addr": "10.180.1.252",
                "type": "N3"
            }
        ]
    },
    "dnnList": [
        {
            "dnn": "internet",
            "cidr": "10.1.0.0/17"
        },
        {
            "dnn": "internet",
            "cidr": "10.1.128.0/17"
        }
    ],
    "logger": {
        "enable": True,
        "level": "info",
        "reportCaller": True
    }
})
