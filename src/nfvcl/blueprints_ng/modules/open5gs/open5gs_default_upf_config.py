from nfvcl_models.blueprint_ng.open5gs.upf import Open5gsUpfConfig

default_upf_config: Open5gsUpfConfig = Open5gsUpfConfig.model_validate({
    "logger": {
        "path": {
            "file": "/opt/open5gs/var/log/open5gs/upf.log"
        },
        "level": "debug"
    },
    "global": None,
    "upf": {
        "pfcp": {
            "server": [
                {
                    "address": "10.180.3.74" #N4
                }
            ],
            "node_id": "10.180.3.74"
        },
        "gtpu": {
            "server": [
                {
                    "address": "10.165.3.66" #N3
                }
            ]
        },
        "session": [
            {
                "subnet": "10.45.0.0/16",
                "gateway": "10.45.0.1",
                "dnn": "internet"
            }
        ]
    }
})
