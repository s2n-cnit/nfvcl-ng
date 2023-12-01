default_config = {
    "mysql": {
        "image": "docker.io/mysql",
        "imageTag": "5.7",
        "replicas": 1,
        "strategy": {
            "type": "Recreate"
        },
        "busybox": {
            "image": "busybox",
            "tag": "latest"
        },
        "testFramework": {
            "enabled": False,
            "image": "bats/bats",
            "tag": "1.2.1",
            "imagePullPolicy": "IfNotPresent",
            "securityContext": {}
        },
        "mysqlRootPassword": "linux",
        "mysqlUser": "test",
        "mysqlPassword": "test",
        "mysqlDatabase": "oai_db",
        "oai5gdatabase": "basic",
        "imagePullPolicy": "IfNotPresent",
        "args": [],
        "extraVolumes": "# - name: extras\n#   emptyDir: {}\n",
        "extraVolumeMounts": "# - name: extras\n#   mountPath: /usr/share/extras\n#   readOnly: true\n",
        "extraInitContainers": "# - name: do-something\n#   image: busybox\n#   command: ['do', 'something']\n",
        "imagePullSecrets": [
            {
                "name": "regcred"
            }
        ],
        "affinity": {},
        "tolerations": [],
        "livenessProbe": {
            "initialDelaySeconds": 50,
            "periodSeconds": 15,
            "timeoutSeconds": 10,
            "successThreshold": 1,
            "failureThreshold": 3
        },
        "readinessProbe": {
            "initialDelaySeconds": 10,
            "periodSeconds": 15,
            "timeoutSeconds": 5,
            "successThreshold": 1,
            "failureThreshold": 3
        },
        "persistence": {
            "enabled": False,
            "accessMode": "ReadWriteOnce",
            "size": "8Gi",
            "annotations": {}
        },
        "securityContext": {
            "enabled": False,
            "runAsUser": 999,
            "fsGroup": 999
        },
        "resources": {
            "requests": {
                "memory": "256Mi",
                "cpu": "100m"
            }
        },
        "configurationFilesPath": "/etc/mysql/conf.d/",
        "configurationFiles": {},
        "mysqlx": {
            "port": {
                "enabled": False
            }
        },
        "metrics": {
            "enabled": False,
            "image": "prom/mysqld-exporter",
            "imageTag": "v0.10.0",
            "imagePullPolicy": "IfNotPresent",
            "resources": {},
            "annotations": {},
            "livenessProbe": {
                "initialDelaySeconds": 15,
                "timeoutSeconds": 5
            },
            "readinessProbe": {
                "initialDelaySeconds": 5,
                "timeoutSeconds": 1
            },
            "flags": [],
            "serviceMonitor": {
                "enabled": False,
                "additionalLabels": {}
            }
        },
        "service": {
            "annotations": {},
            "type": "LoadBalancer",
            "port": 3306
        },
        "serviceAccount": {
            "create": False
        },
        "ssl": {
            "enabled": False,
            "secret": "mysql-ssl-certs",
            "certificates": None
        },
        "deploymentAnnotations": {},
        "podAnnotations": {},
        "podLabels": {},
        "initContainer": {
            "resources": {
                "requests": {
                    "memory": "10Mi",
                    "cpu": "10m"
                }
            }
        }
    },
    "oai-nssf": {
        "kubernetesType": "Vanilla",
        "nfimage": {
            "repository": "docker.io/oaisoftwarealliance/oai-nssf",
            "version": "v1.5.1",
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
            "name": "oai-nssf-sa"
        },
        "podSecurityContext": {
            "runAsUser": 0,
            "runAsGroup": 0
        },
        "config": {
            "tz": "Europe/Paris",
            "logLevel": "debug",
            "instance": "0",
            "nssfname": "oai-nssf",
            "pidDirectory": "/var/run",
            "nssfFqdn": "oai-nssf-svc",
            "sbiIfName": "eth0",
            "sbiPortHttp1": "80",
            "sbiPortHttp2": "8080",
            "sbiApiVersion": "v1",
            "nssfSliceConfig": "/tmp/nssf_slice_config.yaml"
        },
        "start": {
            "nssf": True,
            "tcpdump": False
        },
        "includeTcpDumpContainer": False,
        "tcpdumpimage": {
            "repository": "docker.io/corfr/tcpdump",
            "version": "latest",
            "pullPolicy": "IfNotPresent"
        },
        "persistent": {
            "sharedvolume": True
        },
        "resources": {
            "define": False,
            "limits": {
                "nf": {
                    "cpu": "100m",
                    "memory": "128Mi"
                }
            },
            "requests": {
                "nf": {
                    "cpu": "100m",
                    "memory": "128Mi"
                }
            }
        },
        "readinessProbe": True,
        "livenessProbe": False,
        "terminationGracePeriodSeconds": 5,
        "nodeSelector": {},
        "nodeName": None
    },
    "oai-nrf": {
        "kubernetesType": "Vanilla",
        "nfimage": {
            "repository": "docker.io/oaisoftwarealliance/oai-nrf",
            "version": "v1.5.1",
            "pullPolicy": "IfNotPresent"
        },
        "imagePullSecrets": [
            {
                "name": "regcred"
            }
        ],
        "serviceAccount": {
            "create": True,
            "name": "oai-nrf-sa"
        },
        "podSecurityContext": {
            "runAsUser": 0,
            "runAsGroup": 0
        },
        "config": {
            "nrfInterfaceNameForSBI": "eth0",
            "nrfInterfacePortForSBI": "80",
            "nrfInterfaceHttp2PortForSBI": "8080",
            "nrfApiVersion": "v1",
            "logLevel": "debug"
        },
        "start": {
            "nrf": True,
            "tcpdump": False
        },
        "includeTcpDumpContainer": False,
        "tcpdumpimage": {
            "repository": "docker.io/corfr/tcpdump",
            "version": "latest",
            "pullPolicy": "IfNotPresent"
        },
        "persistent": {
            "sharedvolume": False,
            "storageClass": "-",
            "size": "1Gi"
        },
        "resources": {
            "define": False,
            "limits": {
                "nf": {
                    "cpu": "100m",
                    "memory": "128Mi"
                },
                "tcpdump": {
                    "cpu": "100m",
                    "memory": "128Mi"
                }
            },
            "requests": {
                "nf": {
                    "cpu": "100m",
                    "memory": "128Mi"
                },
                "tcpdump": {
                    "cpu": "100m",
                    "memory": "128Mi"
                }
            }
        },
        "readinessProbe": True,
        "livenessProbe": False,
        "terminationGracePeriodSeconds": 5,
        "nodeSelector": {},
        "nodeName": None
    },
    "oai-udr": {
        "kubernetesType": "Vanilla",
        "nfimage": {
            "repository": "docker.io/oaisoftwarealliance/oai-udr",
            "version": "v1.5.1",
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
            "name": "oai-udr-sa"
        },
        "podSecurityContext": {
            "runAsUser": 0,
            "runAsGroup": 0
        },
        "config": {
            "tz": "Europe/Paris",
            "instance": "0",
            "udrname": "oai-udr",
            "pidDirectory": "/var/run",
            "sbiIfName": "eth0",
            "sbiPortHttp1": "80",
            "sbiPortHttp2": "8080",
            "udrApiVersion": "v1",
            "nrfIpv4Address": "127.0.0.1",
            "nrfPort": "80",
            "nrfApiVersion": "v1",
            "nrfFqdn": "oai-nrf-svc",
            "registerNrf": "no",
            "usehttp2": "no",
            "useFqdnDns": "yes",
            "mySqlServer": "mysql",
            "mySqlUser": "root",
            "mySqlPass": "linux",
            "mySqlDb": "oai_db",
            "logLevel": "debug"
        },
        "start": {
            "udr": True,
            "tcpdump": False
        },
        "includeTcpDumpContainer": False,
        "tcpdumpimage": {
            "repository": "docker.io/corfr/tcpdump",
            "version": "latest",
            "pullPolicy": "IfNotPresent"
        },
        "persistent": {
            "sharedvolume": False
        },
        "resources": {
            "define": False,
            "limits": {
                "nf": {
                    "cpu": "100m",
                    "memory": "128Mi"
                },
                "tcpdump": {
                    "cpu": "100m",
                    "memory": "128Mi"
                }
            },
            "requests": {
                "nf": {
                    "cpu": "100m",
                    "memory": "128Mi"
                },
                "tcpdump": {
                    "cpu": "100m",
                    "memory": "128Mi"
                }
            }
        },
        "readinessProbe": True,
        "livenessProbe": False,
        "terminationGracePeriodSeconds": 5,
        "nodeSelector": {},
        "nodeName": None
    },
    "oai-udm": {
        "kubernetesType": "Vanilla",
        "nfimage": {
            "repository": "docker.io/oaisoftwarealliance/oai-udm",
            "version": "v1.5.1",
            "pullPolicy": "IfNotPresent"
        },
        "imagePullSecrets": [
            {
                "name": "regcred"
            }
        ],
        "serviceAccount": {
            "create": True,
            "name": "oai-udm-sa"
        },
        "podSecurityContext": {
            "runAsUser": 0,
            "runAsGroup": 0
        },
        "config": {
            "tz": "Europe/Paris",
            "instance": 0,
            "pidDirectory": "/var/run",
            "udmName": "oai-udm",
            "logLevel": "debug",
            "sbiIfName": "eth0",
            "sbiPortHttp1": "80",
            "sbiPortHttp2": "8080",
            "udmApiVersionNb": "v1",
            "useFqdnDns": "yes",
            "nfRegistration": "no",
            "useHttp2": "no",
            "udrIpAddress": "127.0.0.1",
            "udrPort": "80",
            "udrApiVersionNb": "v1",
            "udrFqdn": "oai-udr-svc",
            "nrfIpAddress": "127.0.0.1",
            "nrfPort": "80",
            "nrfApiVersionNb": "v1",
            "nrfFqdn": "oai-nrf-svc"
        },
        "start": {
            "udm": True,
            "tcpdump": False
        },
        "includeTcpDumpContainer": False,
        "tcpdumpimage": {
            "repository": "docker.io/corfr/tcpdump",
            "version": "latest",
            "pullPolicy": "IfNotPresent"
        },
        "persistent": {
            "sharedvolume": False
        },
        "resources": {
            "define": False,
            "limits": {
                "nf": {
                    "cpu": "100m",
                    "memory": "128Mi"
                },
                "tcpdump": {
                    "cpu": "100m",
                    "memory": "128Mi"
                }
            },
            "requests": {
                "nf": {
                    "cpu": "100m",
                    "memory": "128Mi"
                },
                "tcpdump": {
                    "cpu": "100m",
                    "memory": "128Mi"
                }
            }
        },
        "readinessProbe": True,
        "livenessProbe": False,
        "terminationGracePeriodSeconds": 5,
        "nodeSelector": {},
        "nodeName": None
    },
    "oai-ausf": {
        "kubernetesType": "Vanilla",
        "nfimage": {
            "repository": "docker.io/oaisoftwarealliance/oai-ausf",
            "version": "v1.5.1",
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
            "name": "oai-ausf-sa"
        },
        "podSecurityContext": {
            "runAsUser": 0,
            "runAsGroup": 0
        },
        "config": {
            "tz": "Europe/Paris",
            "instanceId": "0",
            "pidDirectory": "/var/run",
            "logLevel": "debug",
            "ausfName": "OAI_AUSF",
            "sbiIfName": "eth0",
            "sbiPortHttp1": "80",
            "sbiPortHttp2": "8080",
            "useHttp2": "no",
            "useFqdnDns": "yes",
            "udmIpAddress": "127.0.0.1",
            "udmPort": "80",
            "udmVersionNb": "v1",
            "udmFqdn": "oai-udm-svc",
            "nrfIpAddress": "127.0.0.1",
            "nrfPort": "80",
            "nrfApiVersion": "v1",
            "nrfFqdn": "oai-nrf-svc",
            "registerNrf": "no"
        },
        "start": {
            "ausf": True,
            "tcpdump": False
        },
        "includeTcpDumpContainer": False,
        "tcpdumpimage": {
            "repository": "docker.io/corfr/tcpdump",
            "version": "latest",
            "pullPolicy": "IfNotPresent"
        },
        "persistent": {
            "sharedvolume": False
        },
        "resources": {
            "define": False,
            "limits": {
                "nf": {
                    "cpu": "100m",
                    "memory": "128Mi"
                },
                "tcpdump": {
                    "cpu": "100m",
                    "memory": "128Mi"
                }
            },
            "requests": {
                "nf": {
                    "cpu": "100m",
                    "memory": "128Mi"
                },
                "tcpdump": {
                    "cpu": "100m",
                    "memory": "128Mi"
                }
            }
        },
        "readinessProbe": True,
        "livenessProbe": False,
        "terminationGracePeriodSeconds": 5,
        "nodeSelector": {},
        "nodeName": None
    },
    "oai-amf": {
        "kubernetesType": "Vanilla",
        "nfimage": {
            "repository": "docker.io/oaisoftwarealliance/oai-amf",
            "version": "v1.5.1",
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
            "name": "oai-amf-sa"
        },
        "podSecurityContext": {
            "runAsUser": 0,
            "runAsGroup": 0
        },
        "multus": {
            "defaultGateway": "",
            "n2Interface": {
                "create": False,
                "Ipadd": "172.21.6.94",
                "Netmask": "22",
                "Gateway": None,
                "routes": [
                    {
                        "dst": "10.8.0.0/24",
                        "gw": "172.21.7.254"
                    }
                ],
                "hostInterface": "bond0"
            }
        },
        "config": {
            "logLevel": "debug",
            "amfInterfaceNameForNGAP": "eth0",
            "amfInterfaceNameForSBI": "eth0",
            "amfInterfaceSBIHTTPPort": 80,
            "amfInterfaceSBIHTTP2Port": 8080,
            "mcc": "001",
            "mnc": "01",
            "regionId": "128",
            "amfSetId": "1",
            "tac": "0x0001",
            "sst0": "1",
            "sd0": "0xFFFFFF",
            "sst1": "1",
            "sd1": "1",
            "smfFqdn": "oai-smf-svc",
            "nrfFqdn": "oai-nrf-svc",
            "ausfFqdn": "oai-ausf-svc",
            "nfRegistration": "yes",
            "nrfSelection": "no",
            "smfSelection": "no",
            "externalAusf": "yes",
            "externalUdm": "no",
            "externalNrf": "no",
            "externalNssf": "no",
            "useHttp2": "no",
            "intAlgoList": "[ \"NIA1\" , \"NIA1\" , \"NIA2\" ]",
            "ciphAlgoList": "[ \"NEA0\" , \"NEA1\" , \"NEA2\" ]",
            "mySqlServer": "mysql",
            "mySqlUser": "root",
            "mySqlPass": "linux",
            "mySqlDb": "oai_db"
        },
        "start": {
            "amf": True,
            "tcpdump": False
        },
        "includeTcpDumpContainer": False,
        "tcpdumpimage": {
            "repository": "docker.io/corfr/tcpdump",
            "version": "latest",
            "pullPolicy": "IfNotPresent"
        },
        "persistent": {
            "sharedvolume": False
        },
        "resources": {
            "define": False,
            "limits": {
                "nf": {
                    "cpu": "100m",
                    "memory": "128Mi"
                },
                "tcpdump": {
                    "cpu": "100m",
                    "memory": "128Mi"
                }
            },
            "requests": {
                "nf": {
                    "cpu": "100m",
                    "memory": "128Mi"
                },
                "tcpdump": {
                    "cpu": "100m",
                    "memory": "128Mi"
                }
            }
        },
        "readinessProbe": True,
        "livenessProbe": False,
        "terminationGracePeriodSeconds": 5,
        "nodeSelector": {},
        "nodeName": None
    },
    "oai-smf": {
        "kubernetesType": "Vanilla",
        "nfimage": {
            "repository": "docker.io/oaisoftwarealliance/oai-smf",
            "version": "v1.5.1",
            "pullPolicy": "IfNotPresent"
        },
        "imagePullSecrets": [
            {
                "name": "regcred"
            }
        ],
        "serviceAccount": {
            "create": True,
            "name": "oai-smf-sa"
        },
        "podSecurityContext": {
            "runAsUser": 0,
            "runAsGroup": 0
        },
        "multus": {
            "defaultGateway": "",
            "n4Interface": {
                "create": False,
                "Ipadd": "192.168.24.3",
                "Netmask": "24",
                "Gateway": "",
                "hostInterface": "bond0"
            }
        },
        "config": {
            "smfInterfaceNameForN4": "eth0",
            "smfInterfaceNameForSBI": "eth0",
            "smfInterfacePortForSBI": 80,
            "smfInterfaceHttp2PortForSBI": 8080,
            "smfApiVersion": "v1",
            "httpVersion": 1,
            "defaultCSCFIpv4Address": "172.21.6.96",
            "dnsIpv4Address": "172.21.3.100",
            "dnsSecIpv4Address": "172.21.3.100",
            "upfSpgwu": True,
            "discoverUpf": "yes",
            "useLocalSubscriptionInfo": "no",
            "useFqdnDns": "yes",
            "useLocalPCCRules": "yes",
            "discoverPcf": "no",
            "ueMtu": 1500,
            "registerNrf": "yes",
            "nrfFqdn": "oai-nrf-svc",
            "udmFqdn": "oai-udm-svc",
            "amfFqdn": "oai-amf-svc",
            "dnnNi0": "oai",
            "pdusessiontype0": "IPv4",
            "ipv4dnnRange0": "12.1.1.2 - 12.1.1.254",
            "nssaiSst0": 1,
            "nssaiSd0": "0xFFFFFF",
            "qosProfile5qi0": 2,
            "sessionAmbrUl0": "1000Mbps",
            "sessionAmbrDl0": "1000Mbps",
            "dnnNi1": "ims",
            "pdusessiontype1": "IPv4v6",
            "ipv4dnnRange1": "12.2.1.2 - 12.2.1.254",
            "nssaiSst1": 1,
            "nssaiSd1": "0xFFFFFF",
            "qosProfile5qi1": 1,
            "sessionAmbrUl1": "1000Mbps",
            "sessionAmbrDl1": "1000Mbps",
            "logLevel": "debug"
        },
        "hostAliases": {
            "ip": "10.180.2.41",
            "hostnames": "spgwu.external"
        },
        "start": {
            "smf": True,
            "tcpdump": True
        },
        "includeTcpDumpContainer": False,
        "tcpdumpimage": {
            "repository": "docker.io/corfr/tcpdump",
            "version": "latest",
            "pullPolicy": "IfNotPresent"
        },
        "persistent": {
            "sharedvolume": True
        },
        "resources": {
            "define": False,
            "limits": {
                "nf": {
                    "cpu": "100m",
                    "memory": "128Mi"
                },
                "tcpdump": {
                    "cpu": "100m",
                    "memory": "128Mi"
                }
            },
            "requests": {
                "nf": {
                    "cpu": "100m",
                    "memory": "128Mi"
                },
                "tcpdump": {
                    "cpu": "100m",
                    "memory": "128Mi"
                }
            }
        },
        "readinessProbe": True,
        "livenessProbe": False,
        "terminationGracePeriodSeconds": 5,
        "nodeSelector": {},
        "nodeName": None
    }
}
