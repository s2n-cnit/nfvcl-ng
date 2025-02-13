from nfvcl.models.blueprint_ng.core5g.OAI_Models import OAIUE

# Class representing default config, it will be overwritten with the input one
default_oai_ue_config: OAIUE = OAIUE.model_validate({
    "multus": {
        "create": False,
        "ipAdd": "192.168.22.2",
        "netmask": "24",
        "mac": "",
        "gateway": "",
        "hostInterface": "bond0"
    },
    "config": {
        "timeZone": "Europe/Paris",
        "rfSimServer": "oai-ran",
        "fullImsi": "001010000000100",
        "fullKey": "fec86ba6eb707ed08905757b1bb44b8f",
        "opc": "C42449363BBAD02B66D16BC975D77CC1",
        "dnn": "oai",
        "sst": "1",
        "sd": "16777215",
        "usrp": "rfsim",
        "useAdditionalOptions": "--sa --rfsim -r 106 --numerology 1 -C 3619200000 --log_config.global_log_options level,nocolor,time"
    }
})
