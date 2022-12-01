default_config = {
  "global": {
    "name": "free5gc",
    "projectName": "free5gc",
    "userPlaneArchitecture": "single",
    "nrf": {
      "service": {
        "name": "nrf-nnrf",
        "type": "LoadBalancer",
        "port": 8000
      }
    },
    "sbi": {
      "scheme": "http"
    },
    "amf": {
      "n2if": {
        "ipAddress": "10.100.50.249",
        "interfaceIpAddress": "0.0.0.0"
      },
      "service": {
        "ngap": {
            "enabled": True,
            "name": "amf-n2",
            "port": 38412,
            "protocol": "SCTP",
            "type": "LoadBalancer"
          }
        }
      },

      "smf": {
        "n4if": {
          "ipAddress": "10.100.50.244",
          "interfaceIpAddress": "0.0.0.0"
        }
      },
      "n2network": {
        "name": "n2network",
        "masterIf": "eth0",
        "subnetIP": "10.100.50.248",
        "cidr": "29",
        "gatewayIP": "10.100.50.254",
        "excludeIP": "10.100.50.254"
      },
      "n3network": {
        "name": "n3network",
        "masterIf": "eth0",
        "subnetIP": "10.100.50.232",
        "cidr": "29",
        "gatewayIP": "10.100.50.238",
        "excludeIP": "10.100.50.238"
      },
      "n4network": {
        "name": "n4network",
        "masterIf": "eth0",
        "subnetIP": "10.100.50.240",
        "cidr": "29",
        "gatewayIP": "10.100.50.246",
        "excludeIP": "10.100.50.246"
      },
      "n6network": {
        "name": "n6network",
        "masterIf": "eth1",
        "subnetIP": "10.100.100.0",
        "cidr": "24",
        "gatewayIP": "10.100.100.1",
        "excludeIP": "10.100.100.254"
      },
      "n9network": {
        "name": "n9network",
        "masterIf": "eth0",
        "subnetIP": "10.100.50.224",
        "cidr": "29",
        "gatewayIP": "10.100.50.230",
        "excludeIP": "10.100.50.230"
      }
    },

  "deployMongoDB": True,
  "deployMongoScripts": True,
  "deployAMF": True,
  "deployAUSF": True,
  "deployN3IWF": False,
  "deployNRF": True,
  "deployNSSF": True,
  "deployPCF": True,
  "deploySMF": True,
  "deployUDM": True,
  "deployUDR": True,
  "deployUPF": False,
  "deployWEBUI": True,

  "mongodb": {
    "fullnameOverride": "'mongodb'",
    "useStatefulSet": True,
    "auth": {
      "enabled": False
    },
    "persistence": {
      "size": "6Gi",
      "mountPath": "/bitnami/mongodb/data/db/"
    },
    "service": {
      "name": "mongodb",
      "type": "LoadBalancer",
      "port": 27017,
      "nodePort": 30017
    }
  },

  "free5gc-amf": {
    "amf": {
      "name": "amf",
      "replicaCount": 1,
      "image": {
        "name": "towards5gs/free5gc-amf",
        "pullPolicy": "IfNotPresent"
      },
      "service": {
        "name": "amf-namf",
        "type": "LoadBalancer",
        "port": 80,
        "ngap": {
          "enabled": True,
          "name": "amf-n2",
          "port": 38412,
          "protocol": "SCTP",
          "type": "LoadBalancer"
        }
      },
      "configmap": {
        "name": "amf-configmap"
      },
      "volume": {
        "name": "amf-volume",
        "mount": "/free5gc/config/"
      },
      "podAnnotations": {},
      "imagePullSecrets": [],
      "podSecurityContext": {},
      "securityContext": {},
      "resources": {
        "limits": {
          "cpu": "150m",
          "memory": "128Mi"
        },
        "requests": {
          "cpu": "150m",
          "memory": "128Mi"
        },
      },
      "readinessProbe": {
        "initialDelaySeconds": 0,
        "periodSeconds": 1,
        "timeoutSeconds": 1,
        "failureThreshold": 40,
        "successThreshold": 1,
      },
      "livenessProbe": {
        "initialDelaySeconds": 120,
        "periodSeconds": 10,
        "timeoutSeconds": 10,
        "failureThreshold": 3,
        "successThreshold": 1
      },
      "nodeSelector": {},
      "tolerations": [],
      "affinity": {},
      "autoscaling": {
        "enabled": False,
        "minReplicas": 1,
        "maxReplicas": 100,
        "targetCPUUtilizationPercentage": 80
      },
      "ingress": {
        "enabled": False,
        "annotations": {},
        "hosts": [
          {
            "host": "chart-example.local",
            "paths": []
          }
        ],
        "tls": []
      },
      "configuration": {
        "configuration": "",
        "configurationBase": {
          "reboot": 0,
          "amfName": "AMF",
          "serviceNameList": [
            "namf-comm",
            "namf-evts",
            "namf-mt",
            "namf-loc",
            "namf-oam"
          ],
          "servedGuamiList": [
            {
              "plmnId": {
                "mcc": 208,
                "mnc": 93
              },
              "amfId": "cafe00"
            }
          ],
          "supportTaiList": [
            {
              "plmnId": {
                "mcc": 208,
                "mnc": 93
              },
              "tac": 1
            }
          ],
          "plmnSupportList": [
            {
              "plmnId": {
                "mcc": 208,
                "mnc": 93
              },
              "snssaiList": [
                {
                  "sst": 1,
                  "sd": "010203"
                },
                {
                  "sst": 1,
                  "sd": "112233"
                }
              ],
            }
          ],
          "supportDnnList": [
            "internet"
          ],
          "security": {
            "integrityOrder": [
              "NIA2"
            ],
            "cipheringOrder": [
              "NEA0"
            ]
          },
          "networkName": {
            "full": "free5GC",
            "short": "free"
          },
          # "locality": "area1" # Name of the location where a set of AMF, SMF and UPFs are located
          "networkFeatureSupport5GS": {  # 5gs Network Feature Support IE, refer to TS 24.501
            "enable": True,  # append this IE in Registration accept or not
            "length": 1,
            "imsVoPS": 0,  # IMS voice over PS session indicator (uinteger, range: 0~1)
            "emc": 0,  # Emergency service support indicator for 3GPP access (uinteger, range: 0~3)
            "emf": 0,  # Emergency service fallback indicator for 3GPP access (uinteger, range: 0~3)
            "iwkN26": 0,  # Interworking without N26 interface indicator (uinteger, range: 0~1)
            "mpsi": 0,  # MPS indicator (uinteger, range: 0~1)
            "emcN3": 0,  # Emergency service support indicator for Non-3GPP access (uinteger, range: 0~1)
            "mcsi": 0  # MCS indicator (uinteger, range: 0~1)
          },
          "t3502Value": 720,
          "t3512Value": 3600,
          "non3gppDeregistrationTimerValue": 3240,
          # retransmission timer for paging message
          "t3513": {
            "enable": True,  # true or false
            "expireTime": "6s",  # default is 6 seconds
            "maxRetryTimes": 4  # the max number of retransmission
          },
          # retransmission timer for NAS Registration Accept message
          "t3522": {
            "enable": True,  # true or false
            "expireTime": "6s",  # default is 6 seconds
            "maxRetryTimes": 4  # the max number of retransmission
          },
          # retransmission timer for NAS Registration Accept message
          "t3550": {
            "enable": True,  # true or false
            "expireTime": "6s",  # default is 6 seconds
            "maxRetryTimes": 4,  # the max number of retransmission
          },
          # retransmission timer for NAS Authentication Request/Security Mode Command message
          "t3560": {
            "enable": True,  # true or false
            "expireTime": "6s",  # default is 6 seconds
            "maxRetryTimes": 4  # the max number of retransmission
          },
          # retransmission timer for NAS Notification message
          "t3565": {
            "enable": True,  # true or false
            "expireTime": "6s",  # default is 6 seconds
            "maxRetryTimes": 4  # the max number of retransmission
          },
          # retransmission timer for NAS Identity Request message
          "t3570": {
            "enable": True,  # true or false
            "expireTime": "6s",  # default is 6 seconds
            "maxRetryTimes": 4  # the max number of retransmission
          }
        },
        # the kind of log output
        # debugLevel: how detailed to output, value: trace, debug, info, warn, error, fatal, panic
        # ReportCaller: enable the caller report or not, value: true or false
        "logger": {
          "AMF": {
            "debugLevel": "info",
            "ReportCaller": False
          },
          "NAS": {
            "debugLevel": "info",
            "ReportCaller": False
          },
          "FSM": {
            "debugLevel": "info",
            "ReportCaller": False
          },
          "NGAP": {
            "debugLevel": "info",
            "ReportCaller": False
          },
          "Aper": {
            "debugLevel": "info",
            "ReportCaller": False
          },
          "PathUtil": {
            "debugLevel": "info",
            "ReportCaller": False
          },
          "OpenApi": {
            "debugLevel": "info",
            "ReportCaller": False
          }
        }
      }
    }
  },

  "free5gc-ausf": {
    "ausf": {
      "name": "ausf",
      "replicaCount": 1,
      "image": {
        "name": "towards5gs/free5gc-ausf",
        "tag": "v3.2.0",
        "pullPolicy": "IfNotPresent"
      },
      "service": {
        "name": "ausf-nausf",
        "type": "LoadBalancer",
        "port": 80
      },
      "configmap": {
        "name": "ausf-configmap"
      },
      "volume": {
        "name": "ausf-volume",
        "mount": "/free5gc/config/"
      },
      "podAnnotations": {},
      "imagePullSecrets": [],
      "podSecurityContext": {},
      "securityContext": {},
      "resources": {
        "limits": {
          "cpu": "100m",
          "memory": "128Mi"
        },
        "requests": {
          "cpu": "100m",
          "memory": "128Mi"
        }
      },
      "readinessProbe": {
        "initialDelaySeconds": 0,
        "periodSeconds": 1,
        "timeoutSeconds": 1,
        "failureThreshold":  40,
        "successThreshold": 1
      },
      "livenessProbe": {
        "initialDelaySeconds": 120,
        "periodSeconds": 10,
        "timeoutSeconds": 10,
        "failureThreshold": 3,
        "successThreshold": 1
      },
      "nodeSelector": {},
      "tolerations": [],
      "affinity": {},
      "autoscaling": {
        "enabled": False,
        "minReplicas": 1,
        "maxReplicas": 100,
        "targetCPUUtilizationPercentage": 80
      },
      "ingress": {
        "enabled": False,
        "annotations": {},
        "hosts": [
          {
              "host": "chart-example.local",
              "paths": []
          }
        ],
        "tls": []
      },
      "configuration": {
        "configurationBase": {
          "reboot": 0,
          "serviceNameList": [
            "nausf-auth"
          ],
          "plmnSupportList": [
          {
              "mcc": "208",
              "mnc": "93"
          },
          {
              "mcc": "002",
              "mnc": "02"
          }
          ],
          "groupId": "ausfGroup001"
        },
        "configuration": "",
        "logger": {
          "AUSF": {
            "debugLevel": "info",
            "ReportCaller": False
          },
          "PathUtil": {
            "debugLevel": "info",
            "ReportCaller": False
          },
          "OpenApi": {
            "debugLevel": "info",
            "ReportCaller": False
          }
        }
      }
    }
  },

  "free5gc-n3iwf": {
    "n3iwf": {
      "name": "n3iwf",
      "replicaCount": 1,
      "image": {
        "name": "towards5gs/free5gc-n3iwf",
        "pullPolicy": "IfNotPresent"
      },
      "configmap": {
        "name": "n3iwf-configmap"
      },
      "volume": {
        "name": "n3iwf-volume",
        "mount": "/free5gc/config/"
      },
      # network paramters
      "n2if": {  # NGAP
        "ipAddress": "10.100.50.251"
      },
      "n3if": {  # GTPU
        "ipAddress": "10.100.50.237"
      },
      "ike": {  # define an interface for the IKE daemon as mentioned in the free5gc github README.md
        "ipAddress": "172.16.10.5",
        "name": "ikenetwork",
        "masterIf": "ens3",
        "subnetIP": "172.16.10.0",
        "cidr": 24,
        "gatewayIP": "172.16.10.1"
      },

      "podAnnotations": {},
        # additional annotations
      "imagePullSecrets": [],
      "podSecurityContext": {},
      "securityContext": {
        "capabilities": {
          "add": [
            "NET_ADMIN"
          ]
        }
      },
      "resources": {
        "limits": {
          "cpu": "100m",
          "memory": "128Mi"
        },
        "requests": {
          "cpu": "100m",
          "memory": "128Mi"
        }
      },
      "readinessProbe": {
        "initialDelaySeconds": 0,
        "periodSeconds": 1,
        "timeoutSeconds": 1,
        "failureThreshold":  40,
        "successThreshold": 1
      },
      "livenessProbe": {
        "initialDelaySeconds": 120,
        "periodSeconds": 10,
        "timeoutSeconds": 10,
        "failureThreshold": 3,
        "successThreshold": 1
      },
      "nodeSelector": {},
      "tolerations": [],
      "affinity": {},
      "autoscaling": {
        "enabled": False,
        "minReplicas": 1,
        "maxReplicas": 100,
        "targetCPUUtilizationPercentage": 80
        # targetMemoryUtilizationPercentage: 80
      },

      "configuration": {
        "IPSecInterfaceAddress": "10.0.0.1",
        "configuration": "",
        "configurationBase": {
          "reboot": 0,
          "N3IWFInformation": {
            "GlobalN3IWFID": {
              "PLMNID": {
                "MCC": 208,
                "MNC": 93
              },
              "N3IWFID": 135
            },
            "Name": "free5GC_N3IWF",
            "SupportedTAList": [
              {
                "TAC": "000001",
                "BroadcastPLMNList": [
                  {
                    "PLMNID": {
                      "MCC": 208,
                      "MNC": 93
                    },
                    "TAISliceSupportList": [
                      {
                        "SNSSAI": {
                          "SST": 1,
                          "SD": "010203"
                        }
                      },
                      {
                        "SNSSAI": {
                          "SST": 1,
                          "SD": "112233"
                        }
                      }
                    ]
                  }
                ]
              }
            ]
          },
          # IPSec virtual interface
          "IPSecInterfaceAddress": "10.0.0.1",
          # IPSec virtual interface mark
          "IPSecInterfaceMark": 5,
          # NAS TCP Listen Port
          "NASTCPPort": 20000,
          # N3IWF FQDN
          "FQDN": "n3iwf.free5gc.org",
          # Security
          # Private Key File Path
          "PrivateKey": "",
          # Certificate Authority (CA)
          "CertificateAuthority": "",
          # Certificate
          "Certificate": "",
          # IP address that will be allocated to UE in IPSec tunnel
          "UEIPAddressRange": "10.0.0.0/24",
        },
        # the kind of log output
          # debugLevel: how detailed to output, value: trace, debug, info, warn, error, fatal, panic
          # ReportCaller: enable the caller report or not, value: true or false
        "logger": {
          "N3IWF": {
            "debugLevel": "info",
            "ReportCaller": False
          },
          "NGAP": {
            "debugLevel": "info",
            "ReportCaller": False
          },
          "Aper": {
            "debugLevel": "info",
            "ReportCaller": False
          },
          "PathUtil": {
            "debugLevel": "info",
            "ReportCaller": False
          }
        }
      }
    }
  },

  "free5gc-nrf": {
    "db": {
      "enabled": False
    },
    "nrf": {
      "name": "nrf",
      "replicaCount": 1,
      "image": {
        "name": "towards5gs/free5gc-nrf",
        "tag": "v3.2.0",
        "pullPolicy": "IfNotPresent"
      },
      "configmap": {
        "name": "nrf-configmap"
      },
      "volume": {
        "name": "nrf-volume",
        "mount": "/free5gc/config/"
      },
      "podAnnotations": {},
      "imagePullSecrets": [],
      "podSecurityContext": {},
      "securityContext": {},
      "resources": {
        "limits": {
          "cpu": "100m",
          "memory": "128Mi"
        },
        "requests": {
          "cpu": "100m",
          "memory": "128Mi"
        }
      },
      "readinessProbe": {
        "initialDelaySeconds": 0,
        "periodSeconds": 1,
        "timeoutSeconds": 1,
        "failureThreshold":  40,
        "successThreshold": 1
      },
      "livenessProbe": {
        "initialDelaySeconds": 120,
        "periodSeconds": 10,
        "timeoutSeconds": 10,
        "failureThreshold": 3,
        "successThreshold": 1
      },
      "nodeSelector": {},
      "tolerations": [],
      "affinity": {},
      "autoscaling": {
        "enabled": False,
        "minReplicas": 1,
        "maxReplicas": 100,
        "targetCPUUtilizationPercentage": 80
      },
      "ingress": {
        "enabled": False,
        "annotations": {},
        "hosts": [
            {
                "host": "chart-example.local",
                "paths": []
            }
        ],
        "tls": []
      },
      "configuration": {
        "configuration": "",
        "configurationBase": {
          "reboot": 0,
          "DefaultPlmnId": {
            "mcc": 208,
            "mnc": 93
          },
          "serviceNameList": [
            "nnrf-nfm",
            "nnrf-disc"
          ]
        },
        "logger": {
          "NRF": {
            "debugLevel": "info",
            "ReportCaller": False
          },
          "PathUtil": {
            "debugLevel": "info",
            "ReportCaller": False
          },
          "OpenApi": {
            "debugLevel": "info",
            "ReportCaller": False
          },
          "MongoDBLibrary": {
            "debugLevel": "info",
            "ReportCaller": False
          }
        }
      }
    }
  },

  "free5gc-nssf": {
    "nssf": {
      "name": "nssf",
      "replicaCount": 1,
      "image": {
        "name": "towards5gs/free5gc-nssf",
        "tag": "v3.2.0",
        "pullPolicy": "IfNotPresent"
      },
      "service": {
        "name": "nssf-nnssf",
        "type": "LoadBalancer",
        "port": 80
      },
      "configmap": {
        "name": "nssf-configmap"
      },
      "volume": {
        "name": "nssf-volume",
        "mount": "/free5gc/config/"
      },
      "podAnnotations": {},
      "imagePullSecrets": [],
      "podSecurityContext": {},
      "securityContext": {},
      "resources": {
        "limits": {
          "cpu": "100m",
          "memory": "128Mi"
        },
        "requests": {
          "cpu": "100m",
          "memory": "128Mi"
        }
      },
      "readinessProbe": {
        "initialDelaySeconds": 0,
        "periodSeconds": 1,
        "timeoutSeconds": 1,
        "failureThreshold":  40,
        "successThreshold": 1
      },

      "livenessProbe": {
        "initialDelaySeconds": 120,
        "periodSeconds": 10,
        "timeoutSeconds": 10,
        "failureThreshold": 3,
        "successThreshold": 1
      },
      "nodeSelector": {},
      "tolerations": [],
      "affinity": {},
      "autoscaling": {
        "enabled": False,
        "minReplicas": 1,
        "maxReplicas": 100,
        "targetCPUUtilizationPercentage": 80
      },
      "ingress": {
        "enabled": False,
        "annotations": {},
        "hosts": [
            {
              "host": "chart-example.local",
              "paths": []
            }
        ],
        "tls": []
      },
      "configuration": {
        "configuration": "",
        "configurationBase": {
          "reboot": 0,
          "nssfName": "NSSF",
          "nrfUri": "http://nrf-nnrf:8000",
          "serviceNameList": [
            "nnssf-nsselection",
            "nnssf-nssaiavailability"
          ],
          "supportedPlmnList": [
              {
                  "mcc": 208,
                  "mnc": 93
              }
          ],
          "supportedNssaiInPlmnList": [
              {
                  "plmnId": {
                     "mcc": 208,
                     "mnc": 93
                   },
                  "supportedSnssaiList": [
                      {
                          "sst": 1,
                          "sd": "010203"
                      },
                      {
                          "sst": 1,
                          "sd": "112233"
                      },
                      {
                          "sst": 1,
                          "sd": "3"
                      },
                      {
                          "sst": 2,
                          "sd": "1"
                      },
                      {
                          "sst": 1,
                          "sd": "1"
                      }
                  ]
              }
          ],
          "amfList": [
              {
                  "nfId": "469de254-2fe5-4ca0-8381-af3f500af77c",
                  "supportedNssaiAvailabilityData": [
                      {
                          "tai": {
                              "plmnId": {
                                  "mcc": 466,
                                  "mnc": 92
                               },
                              "tac": 33456
                           },
                           "supportedSnssaiList": [
                               {
                                   "sst": 1
                               },
                               {
                                   "sst": 1,
                                   "sd": 2
                               },
                               {
                                   "sst": 2
                               }
                           ]
                       }
                    ]
               }
          ],
          "taList": [
            {
              "tai": {
                "plmnId": {
                  "mcc": 466,
                  "mnc": 92
                },
                "tac": 33456
              },
              "accessType": "3GPP_ACCESS",
              "supportedSnssaiList": [
                {
                  "sst": 1
                },
                {
                  "sst": 1,
                  "sd": 1
                },
                {
                  "sst": 1,
                  "sd": 2
                },
                {
                  "sst": 2
                }
              ]
            }
          ],
          "mappingListFromPlmn": [
            {
              "operatorName": "NTT Docomo",
              "homePlmnId": {
                "mcc": 440,
                "mnc": 10
              },
              "mappingOfSnssai": [
                {
                  "servingSnssai": {
                    "sst": 1,
                    "sd": 1
                  },
                  "homeSnssai": {
                    "sst": 1,
                    "sd": 1
                   }
                },
                {
                  "servingSnssai": {
                    "sst": 1,
                    "sd": 2
                  },
                  "homeSnssai": {
                    "sst": 1,
                    "sd": 3
                  }
                },
                {
                  "servingSnssai": {
                    "sst": 1,
                    "sd": 3
                  },
                  "homeSnssai": {
                    "sst": 1,
                    "sd": 4
                  }
                },
                {
                  "servingSnssai": {
                    "sst": 2,
                    "sd": 1
                  },
                  "homeSnssai": {
                    "sst": 2,
                    "sd": 2
                  }
                }
               ]
            }
            ]
        },
        "logger": {
          "NSSF": {
            "debugLevel": "info",
            "ReportCaller": False
          },
          "PathUtil": {
            "debugLevel": "info",
            "ReportCaller": False
          },
          "OpenApi": {
            "debugLevel": "info",
            "ReportCaller": False
          }
        }
      }
    }
  },

  "free5gc-pcf": {
    "pcf": {
      "name": "pcf",
      "replicaCount": 1,
      "image": {
        "name": "towards5gs/free5gc-pcf",
        "pullPolicy": "IfNotPresent",
        "tag": "v3.2.0"
      },
      "service": {
        "name": "pcf-npcf",
        "type": "LoadBalancer",
        "port": 80
      },
      "configmap": {
        "name": "pcf-configmap"
      },
      "volume": {
        "name": "pcf-volume",
        "mount": "/free5gc/config/"
      },
      "podAnnotations": {},
      "imagePullSecrets": [],
      "podSecurityContext": {},
      "securityContext": {},
      "resources": {
        "limits": {
          "cpu": "100m",
          "memory": "128Mi"
        },
        "requests": {
          "cpu": "100m",
          "memory": "128Mi"
        }
      },
      "readinessProbe": {
        "initialDelaySeconds": 0,
        "periodSeconds": 1,
        "timeoutSeconds": 1,
        "failureThreshold":  40,
        "successThreshold": 1
      },
      "livenessProbe": {
        "initialDelaySeconds": 120,
        "periodSeconds": 10,
        "timeoutSeconds": 10,
        "failureThreshold": 3,
        "successThreshold": 1
      },
      "nodeSelector": {},
      "tolerations": [],
      "affinity": {},
      "autoscaling": {
        "enabled": False,
        "minReplicas": 1,
        "maxReplicas": 100,
        "targetCPUUtilizationPercentage": 80
      },
      "ingress": {
        "enabled": False,
        "annotations": {},
        "hosts": [
            {
                "host": "chart-example.local",
                "paths": []
            }
        ],
        "tls": [],
      },
      "configuration": {
        "configuration": "",
        "configurationBase": {
          "reboot": 0,
          "pcfName": "PCF",
          "timeFormat": "2019-01-02 15:04:05",
          "defaultBdtRefId": "BdtPolicyId-",
          "serviceList": [
            {
                "serviceName": "npcf-am-policy-control"
            },
            {
                "serviceName": "npcf-smpolicycontrol",
                "suppFeat": "3fff"
            },
            {
                "serviceName": "npcf-bdtpolicycontrol"
            },
            {
                "serviceName": "npcf-policyauthorization",
                "suppFeat": 3
            },
            {
                "serviceName": "npcf-eventexposure"
            },
            {
                "serviceName": "npcf-ue-policy-control"
            }
          ]
        },
        "logger": {
          "PCF": {
            "debugLevel": "info",
            "ReportCaller": False
          },
          "PathUtil": {
            "debugLevel": "info",
            "ReportCaller": False
          },
          "OpenApi": {
            "debugLevel": "info",
            "ReportCaller": False
          }
        }
      }
    }
  },

  "free5gc-smf": {
    "smf": {
      "name": "smf",
      "replicaCount": 1,
      "image": {
        "name": "towards5gs/free5gc-smf",
        "pullPolicy": "IfNotPresent"
      },
      "service": {
        "name": "smf-nsmf",
        "type": "LoadBalancer",
        "port": 80
      },
      "configmap": {
        "name": "smf-configmap"
      },
      "volume": {
        "name": "smf-volume",
        "mount": "/free5gc/config/"
      },
      "podAnnotations": {},
        # additional annotations
      "imagePullSecrets": [],
      "podSecurityContext": {},
      "securityContext": {},
      "resources": {
        "limits": {
          "cpu": "100m",
          "memory": "128Mi"
        },
        "requests": {
          "cpu": "100m",
          "memory": "128Mi"
        }
      },
      "readinessProbe": {
        "initialDelaySeconds": 0,
        "periodSeconds": 1,
        "timeoutSeconds": 1,
        "failureThreshold":  40,
        "successThreshold": 1
      },
      "livenessProbe": {
        "initialDelaySeconds": 120,
        "periodSeconds": 10,
        "timeoutSeconds": 10,
        "failureThreshold": 3,
        "successThreshold": 1
      },
      "nodeSelector": {},
      "tolerations": [],
      "affinity": {},
      "autoscaling": {
        "enabled": False,
        "minReplicas": 1,
        "maxReplicas": 100,
        "targetCPUUtilizationPercentage": 80
        # targetMemoryUtilizationPercentage: 80
      },
      "ingress": {
        "enabled": False,
        "annotations": {},
          # kubernetes.io/ingress.class: nginx
          # kubernetes.io/tls-acme: "true"
        "hosts": [
          {
            "host": "chart-example.local",
            "paths": []
          }
        ],
        "tls": [],
        #  - secretName: chart-example-tls
        #    hosts:
        #      - chart-example.local
      },
      "configuration": {
        "configuration": "",
        "configurationBase": {
          "reboot": 0,
          "smfName": "SMF",
          "serviceNameList": [
            "nsmf-pdusession",
            "nsmf-event-exposure",
            "nsmf-oam"
          ],
          "snssaiInfos": [
            {
              "sNssai": {
                "sst": 1,
                "sd": "010203"
              },
              "dnnInfos": [ # DNN information list
                {
                  "dnn": "internet", # Data Network Name
                  "dns": {# the IP address of DNS
                    "ipv4": "8.8.8.8"
                  }
                }
              ]
            }
          ],
          "plmnList": [ # the list of PLMN IDs that this SMF belongs to (optional, remove this key when unnecessary)
            {
              "mcc": "208", # Mobile Country Code (3 digits string, digit: 0~9)
              "mnc": "93" # Mobile Network Code (2 or 3 digits string, digit: 0~9)
            }
          ]
        },
        "ueRoutingInfo": "",
        "ueRoutingInfoBase": {
          "UE1": { # Group Name
            "members": [
              "imsi-208930000000003" # Subscription Permanent Identifier of the UE
            ],
            "topology": [ # Network topology for this group (Uplink: A->B, Downlink: B->A)
            # default path derived from this topology
            # node name should be consistent with smfcfg.yaml
              {
                "A": "gNB1",
                "B": "BranchingUPF"
              },
              {
                "A": "BranchingUPF",
                "B": "AnchorUPF1"
              }
            ],
            "specificPath": [
              {
                "dest": "10.100.100.26/32", # the destination IP address on Data Network (DN)
                # the order of UPF nodes in this path. We use the UPF's name to represent each UPF node.
                # The UPF's name should be consistent with smfcfg.yaml
                "path": [
                  "BranchingUPF",
                  "AnchorUPF2"
                ]
              }
            ],
          },
          "UE2": { # Group Name
            "members": [
              "imsi-208930000000004" # Subscription Permanent Identifier of the UE
            ],
            "topology": [ # Network topology for this group (Uplink: A->B, Downlink: B->A)
            # default path derived from this topology
            # node name should be consistent with smfcfg.yaml
              {
                "A": "gNB1",
                "B": "BranchingUPF"
              },
              {
                "A": "BranchingUPF",
                "B": "AnchorUPF1"
              }
            ],
            "specificPath": [
              {
                "dest": "10.100.100.16/32", # the destination IP address on Data Network (DN)
                # the order of UPF nodes in this path. We use the UPF's name to represent each UPF node.
                # The UPF's name should be consistent with smfcfg.yaml
                "path": [
                  "BranchingUPF",
                  "AnchorUPF2"
                ]
              }
            ]
          }
        },
        "logger": {
          "SMF": {
            "debugLevel": "info",
            "ReportCaller": False
          },
          "NAS": {
            "debugLevel": "info",
            "ReportCaller": False
          },
          "NGAP": {
            "debugLevel": "info",
            "ReportCaller": False
          },
          "Aper": {
            "debugLevel": "info",
            "ReportCaller": False
          },
          "PathUtil": {
            "debugLevel": "info",
            "ReportCaller": False
          },
          "OpenApi": {
            "debugLevel": "info",
            "ReportCaller": False
          },
          "PFCP": {
            "debugLevel": "info",
            "ReportCaller": False
          }
        }
      }
    }
  },

  "free5gc-udm": {
    "udm": {
      "name": "udm",
      "replicaCount": 1,
      "image": {
        "name": "towards5gs/free5gc-udm",
        "tag": "v3.2.0",
        "pullPolicy": "IfNotPresent"
      },
      "service": {
        "name": "udm-nudm",
        "type": "LoadBalancer",
        "port": 80
      },
      "configmap": {
        "name": "udm-configmap"
      },
      "volume": {
        "name": "udm-volume",
        "mount": "/free5gc/config/"
      },
      "podAnnotations": {},
      "imagePullSecrets": [],
      "podSecurityContext": {},
      "securityContext": {},
      "resources": {
        "limits": {
          "cpu": "100m",
          "memory": "128Mi"
        },
        "requests": {
          "cpu": "100m",
          "memory": "128Mi"
        }
      },
      "readinessProbe": {
        "initialDelaySeconds": 0,
        "periodSeconds": 1,
        "timeoutSeconds": 1,
        "failureThreshold": 40,
        "successThreshold": 1
      },
      "livenessProbe": {
        "initialDelaySeconds": 120,
        "periodSeconds": 10,
        "timeoutSeconds": 10,
        "failureThreshold": 3,
        "successThreshold": 1
      },
      "nodeSelector": {},
      "tolerations": [],
      "affinity": {},
      "autoscaling": {
        "enabled": False,
        "minReplicas": 1,
        "maxReplicas": 100,
        "targetCPUUtilizationPercentage": 80
      },
      "ingress": {
        "enabled": False,
        "annotations": {},
        "hosts": [
          {
            "host": "chart-example.local",
            "paths": [],
            "tls": []
          }
        ]
      },
      "configuration": {
        "configuration": "",
        "configurationBase": {
          "reboot": 0,
          "serviceNameList": [
            "nudm-sdm",
            "nudm-uecm",
            "nudm-ueau",
            "nudm-ee",
            "nudm-pp"
          ],
          "SuciProfile": [
            {
              "ProtectionScheme": 1,
              "PrivateKey": "c53c22208b61860b06c62e5406a7b330c2b577aa5558981510d128247d38bd1d",
              "PublicKey": "5a8d38864820197c3394b92613b20b91633cbd897119273bf8e4a6f4eec0a650"
            },
            {
              "ProtectionScheme": 2,
              "PrivateKey": "F1AB1074477EBCC7F554EA1C5FC368B1616730155E0041AC447D6301975FECDA",
              "PublicKey": "0472DA71976234CE833A6907425867B82E074D44EF907DFB4B3E21C1C2256EBCD15A7DED52FCBB097A4ED250E036C7B9C8C7004C4EEDC4F068CD7BF8D3F900E3B4"
            }
          ]
        },
        "logger": {
          "UDM": {
            "debugLevel": "info",
            "ReportCaller": False
          },
          "OpenApi": {
            "debugLevel": "info",
            "ReportCaller": False
          },
          "PathUtil": {
            "debugLevel": "info",
            "ReportCaller": False
          }
        }
      }
    }
  },

  "free5gc-udr": {
    "udr": {
      "name": "udr",
      "replicaCount": 1,
      "image": {
        "name": "towards5gs/free5gc-udr",
        "pullPolicy": "IfNotPresent",
        "tag": "v3.2.0",
      },
      "service": {
        "name": "udr-nudr",
        "type": "LoadBalancer",
        "port": 80
      },
      "configmap": {
        "name": "udr-configmap"
      },
      "volume": {
        "name": "udr-volume",
        "mount": "/free5gc/config/"
      },
      "podAnnotations": {},
      "imagePullSecrets": [],
      "podSecurityContext": {},
      "securityContext": {},
      "resources": {
        "limits": {
          "cpu": "100m",
          "memory": "128Mi"
        },
        "requests": {
          "cpu": "100m",
          "memory": "128Mi"
        }
      },
      "readinessProbe": {
        "initialDelaySeconds": 0,
        "periodSeconds": 1,
        "timeoutSeconds": 1,
        "failureThreshold": 40,
        "successThreshold": 1
      },
      "livenessProbe": {
        "initialDelaySeconds": 120,
        "periodSeconds": 10,
        "timeoutSeconds": 10,
        "failureThreshold": 3,
        "successThreshold": 1
      },
      "nodeSelector": {},
      "tolerations": [],
      "affinity": {},
      "autoscaling": {
        "enabled": False,
        "minReplicas": 1,
        "maxReplicas": 100,
        "targetCPUUtilizationPercentage": 80
      },
      "ingress": {
        "enabled": False,
        "annotations": {},
        "hosts": [
          {
            "host": "chart-example.local",
            "paths": []
          }
        ],
        "tls": []
      },
      "configuration": {
        "configuration": "",
        "configurationBase": {
          "reboot": 0,
        },
        "logger": {
          "UDR": {
            "debugLevel": "info",
            "ReportCaller": False
          },
          "MongoDBLibrary": {
            "debugLevel": "info",
            "ReportCaller": False
          },
          "PathUtil": {
            "debugLevel": "info",
            "ReportCaller": False
          },
          "OpenApi": {
            "debugLevel": "info",
            "ReportCaller": False
          }
        }
      }
    }
  },

  "free5gc-webui": {
    "webui": {
      "name": "webui",
      "replicaCount": 1,
      "image": {
        "name": "towards5gs/free5gc-webui",
        "tag": "v3.2.0",
        "pullPolicy": "IfNotPresent"
      },
      "service": {
        "name": "webui-service",
        "type": "LoadBalancer",
        "port": 5000
      },
      "configmap": {
        "name": "webui-configmap"
      },
      "volume": {
        "name": "webui-volume",
        "mount": "/free5gc/config/"
      },
      "podAnnotations": {},
      "imagePullSecrets": [],
      "podSecurityContext": {},
      "securityContext": {},
      "resources": {
        "limits": {
          "cpu": "100m",
          "memory": "128Mi"
        },
        "requests": {
          "cpu": "100m",
          "memory": "128Mi"
        }
      },
      "readinessProbe": {
        "initialDelaySeconds": 0,
        "periodSeconds": 1,
        "timeoutSeconds": 1,
        "failureThreshold":  40,
        "successThreshold": 1
      },
      "livenessProbe": {
        "initialDelaySeconds": 120,
        "periodSeconds": 10,
        "timeoutSeconds": 10,
        "failureThreshold": 3,
        "successThreshold": 1
      },
      "nodeSelector": {},
      "tolerations": [],
      "affinity": {},
      "autoscaling": {
        "enabled": False,
        "minReplicas": 1,
        "maxReplicas": 100,
        "targetCPUUtilizationPercentage": 80
      },
      "ingress": {
        "enabled": False,
        "annotations": {},
        "hosts": [
            {
                "host": "chart-example.local",
                "paths": []
            }
        ],
        "tls": []
      },
      "configuration": {
        "reboot": 0,
        "logger": {
          "WEBUI": {
            "debugLevel": "info",
            "ReportCaller": True
          },
          "PathUtil": {
            "debugLevel": "info",
            "ReportCaller": False
          },
          "OpenApi": {
            "debugLevel": "info",
            "ReportCaller": False
          },
          "MongoDBLibrary": {
            "debugLevel": "info",
            "ReportCaller": False
          }
        }
      }
    }
  }
}
