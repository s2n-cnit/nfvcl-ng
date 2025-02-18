from nfvcl_models.blueprint_ng.core5g.OAI_Models import GNB

default_gnb_config: GNB = GNB.model_validate({
    "kubernetesDistribution": "Vanilla",
    "nfimage": {
        "repository": "docker.io/oaisoftwarealliance/oai-gnb",
        "version": "2024.w32",
        "pullPolicy": "IfNotPresent"
    },
    "imagePullSecrets": [
        {
            "name": "regcred"
        }
    ],
    "serviceAccount": {
        "create": True,
        "annotations": {},
        "name": "oai-gnb-sa"
    },
    "multus": {
        "defaultGateway": "",
        "n2Interface": {
            "create": False,
            "ipAdd": "172.21.8.95",
            "netmask": "22",
            "name": "n2",
            "mac": "",
            "gateway": "",
            "routes": [],
            "hostInterface": "bond0"
        },
        "n3Interface": {
            "create": False,
            "ipAdd": "172.21.8.96",
            "netmask": "22",
            "name": "n3",
            "mac": "",
            "gateway": "",
            "routes": [],
            "hostInterface": "bond0"
        },
        "ru1Interface": {
            "create": False,
            "ipAdd": "192.168.80.90",
            "netmask": "22",
            "name": "ru1",
            "mac": "",
            "gateway": "",
            "routes": [],
            "hostInterface": "bond0"
        },
        "ru2Interface": {
            "create": False,
            "ipAdd": "192.168.80.91",
            "netmask": "22",
            "name": "ru2",
            "mac": "",
            "gateway": "",
            "routes": [],
            "hostInterface": "bond0"
        }
    },
    "config": {
        "timeZone": "Europe/Paris",
        "useAdditionalOptions": "--sa --rfsim --log_config.global_log_options level,nocolor,time",
        "gnbName": "oai-gnb-rfsim",
        "mcc": "001",
        "mnc": "01",
        "tac": "1",
        "sst": "1",
        "sd": "000001",
        "usrp": "rfsim",
        "n2IfName": "eth0",
        "n3IfName": "eth0",
        "amfIpAddress": "oai-amf"
    },
    "start": {
        "gnb": True,
        "tcpdump": False
    },
    "includeTcpDumpContainer": False,
    "podSecurityContext": {
        "runAsUser": 0,
        "runAsGroup": 0
    },
    "securityContext": {
        "privileged": False
    },
    "tcpdumpimage": {
        "repository": "docker.io/oaisoftwarealliance/oai-tcpdump-init",
        "version": "alpine-3.20",
        "pullPolicy": "IfNotPresent"
    },
    "persistent": {
        "sharedvolume": False,
        "volumeName": "oai5g-volume",
        "size": "1Gi"
    },
    "resources": {
        "define": False,
        "limits": {
            "nf": {
                "cpu": "2000m",
                "memory": "2Gi"
            },
            "tcpdump": {
                "cpu": "200m",
                "memory": "128Mi"
            }
        },
        "requests": {
            "nf": {
                "cpu": "2000m",
                "memory": "2Gi"
            },
            "tcpdump": {
                "cpu": "100m",
                "memory": "128Mi"
            }
        }
    },
    "tolerations": [],
    "affinity": {},
    "terminationGracePeriodSeconds": 5,
    "nodeSelector": {},
    "nodeName": None
})
