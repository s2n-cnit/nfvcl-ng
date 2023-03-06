default_config = {
    "open5gs":
    {
        "image":
            {
                "repository": "registry.gitlab.com/infinitydon/registry/open5gs-aio",
                "pullPolicy": "IfNotPresent",
                "tag": "v2.2.6"
            }
    },

    "webui":
    {
        "image":
        {
            "repository": "registry.gitlab.com/infinitydon/registry/open5gs-webui",
            "pullPolicy": "IfNotPresent",
            "tag": "v2.2.6"
        },
        "ingress":
        {
            "enabled": False,
            "hosts":
            [
                {
                    "name": "open5gs-epc.local",
                    "paths": ["/"],
                    "tls": False
                }
            ]
        }
    },

    "filebeat":
    {
        "image":
        {
            "repository": "docker.elastic.co/beats/filebeat",
            "pullPolicy": "IfNotPresent",
            "tag": "7.15.0"
        }
    },

    "packetbeat":
    {
        "image":
            {
                "repository": "docker.elastic.co/beats/packetbeat",
                "pullPolicy": "IfNotPresent",
                "tag": "7.15.0",
            }
    },

    "remoteLogstash":
    {
        "address": "localhost",
        "port": "5044",
    },

    "n1_net": "mngmnt-vnf",
    "mgt_net": "mngmnt-vnf",
    "dnn_net": "mngmnt-vnf",

    "dnn": "internet",

    "mcc": "001",
    "mnc": "01",
    "tac": "0001",

    "k8s":
    {
        "interface": "eth0"
    },

    "amf":
    {
        "mcc": "'{{ .Values.mcc }}'",
        "mnc": "'{{ .Values.mnc }}'",
        "tac": "'{{ .Values.tac }}'",
    },

    "amfconfigmap":
    {
        "logger":
        {
            "file": "/var/log/open5gs/amf.log"
        },

        "amf":
        {
            "sbi":
                [
                    {
                        "addr": "0.0.0.0",
                        "advertise": "{{ include \"open5gs.fullname\" . }}-amf"
                    }
                ],
            "ngap":
                {
                    "dev": "'{{ .Values.k8s.interface }}'"
                },
            "guami":
                [
                    {
                        "plmn_id":
                            {
                                "mcc": "'{{ .Values.mcc }}'",
                                "mnc": "'{{ .Values.mnc }}'"
                            },
                        "amf_id":
                            {
                                "region": 2,
                                "set": 1
                            }
                    }
                ],
            "tai":
            [
                {
                    "plmn_id":
                    {
                        "mcc": "'{{ .Values.mcc }}'",
                        "mnc": "'{{ .Values.mnc }}'"
                    },
                    "tac": "'{{ .Values.tac }}'"
                }
            ],
            "plmn_support":
            [
                {
                    "plmn_id":
                        {
                            "mcc": "'{{ .Values.mcc }}'",
                            "mnc": "'{{ .Values.mnc }}'"
                        },
                    "s_nssai":
                        [
                            {
                                "sst": 1,
                                "sd": 1
                            }
                        ]
                }
            ],
            "security":
            {
                "integrity_order":
                    [
                        "NIA2",
                        "NIA1",
                        "NIA0"
                    ],
                "ciphering_order":
                    [
                        "NEA0",
                        "NEA1",
                        "NEA2"
                    ]
            },
            "network_name":
            {
                "full": "Open5GS"
            },
            "amf_name": "open5gs-amf0"
        },

        "nrf":
        {
            "sbi":
                {
                    "name": "{{ include \"open5gs.fullname\" . }}-nrf"
                }
        }
    },

    "ausfconfigmap":
    {
        "logger":
        {
            "file": "/var/log/open5gs/ausf.log"
        },
        "ausf":
        {
            "sbi":
            [
                {
                    "addr": "0.0.0.0",
                    "advertise": "{{ include \"open5gs.fullname\" . }}-ausf"
                }
            ]
        },
        "nrf":
        {
            "sbi":
                {
                    "name": "{{ include \"open5gs.fullname\" . }}-nrf"
                }
        }
    },

    "filebeatconfigmap": {
        "filebeat" : { "modules" : ""},

        "filebeat" : { "inputs":
        [
            {
                "type": "log",
                "enabled": True,
                "paths": "'${LOG_PATHS}'"
            }
        ]},

        "output" :
        {"elasticsearch":
            {
                "enabled": False,
                "hosts":
                [
                    "localhost:9200"
                ]
            }
        },

        "output":
        {
        "logstash":
        {
            "enabled": True,
            "hosts":
            [
                "${REMOTE_LOGSTASH_ADDRESS}:${REMOTE_LOGSTASH_PORT}"
            ]
        }
        },
        "logging": {"level": "info"},
        "logging": {"to_files": True},

        "logging" :
        {"files":
        {
            "path": "/var/log/filebeat",
            "name": "filebeat"
        }
        }
    },

    "hssconfigmap":
    {
        "db_uri": "mongodb://{{ include \"open5gs.fullname\" . }}-mongodb-svc/open5gs",
        "logger":
        {
            "level": "debug"
        },
        "hss":
        {
            "freeDiameter": "hss.conf"
        }
    },

    "mmeconfigmap":
    {
        "db_uri": "mongodb://{{ include \"open5gs.fullname\" . }}-mongodb-svc/open5gs",
        "logger":
        {
            "level": "debug"
        },

        "mme":
        {
            "freeDiameter": "mme.conf",
            "s1ap":
            [
                {
                    "dev": "eth0"
                }
            ],
            "gtpc":
            [
                {"dev": "eth0"}
            ],
            "gummei":
            {
            "plmn_id":
            {
                "mcc": "'{{ .Values.mcc }}'",
                "mnc": "'{{ .Values.mnc }}'"
            },
            "mme_gid": 2,
            "mme_code": 1
            },
            "tai":
            {
                "plmn_id":
                {
                    "mcc": "'{{ .Values.mcc }}'",
                    "mnc": "'{{ .Values.mnc }}'"
                },
                "tac": "'{{ .Values.tac }}'"
            },
            "security":
            {
            "integrity_order":
            [
                "EIA1",
                "EIA2",
                "EIA0"
            ],
            "ciphering_order":
            [
                "EEA0",
                "EEA1",
                "EEA2"
            ]
            },
            "network_name":
            {
                "full": "Open5GS"
            }
        },

        "sgwc":
        {
            "gtpc":
            [
                {
                    "name": "{{ include \"open5gs.fullname\" . }}-sgwc"
                }
            ]
        },

        "smf":
        {
            "gtpc":
            [
                {
                    "name": "{{ include \"open5gs.fullname\" . }}-smf"
                }
            ]
        }
    },

    "nrfconfigmap":
    {
        "logger":
        {
            "file": "/var/log/open5gs/nrf.log"
        },
        "nrf":
        {
            "sbi":
            {
                "addr": "0.0.0.0"
            }
        }
    },

    "nssfconfigmap":
    {
        "logger":
        {
            "file": "/var/log/open5gs/nssf.log"
        },

        "nssf":
        {
        "sbi":
        [
            {
                "addr": "0.0.0.0",
                "advertise": "{{ include \"open5gs.fullname\" . }}-nssf"
            }
        ],
        "nsi":
        [
            {
                "addr": "{{ include \"open5gs.fullname\" . }}-nrf",
                "port": 80,
                "s_nssai":
                {
                    "sst": 1,
                    "sd": 1
                }
            }
        ]
        },
        "nrf":
        {
            "sbi":
            {
                "name": "{{ include \"open5gs.fullname\" . }}-nrf"
            }
        }
    },

    "packetbeatconfigmap":
    {
        "packetbeat": { "interfaces" : { "device": "any"}},
        "packetbeat": { "interfaces" : { "internal_networks" :
        [
            "private"
        ]}},

        "packetbeat": { "flows":
        {
            "timeout": "30s",
            "period": "10s",
        }},

        "packetbeat" : {"protocols":
        [
            {
                "type": "icmp"
            },
            {
                "type": "amqp",
                "ports":
                    [
                        5672
                    ]
            },
            {
                "type": "cassandra",
                "ports":
                    [
                        9042
                    ]
            },
            {
                "type": "dhcpv4",
                "ports":
                    [
                        67,
                        68
                    ]
            },
            {
                "type": "dns",
                "ports":
                    [
                        53
                    ],
                "include_authorities": True,
                "include_additionals": True
            },
            {
                "type": "http",
                "ports":
                    [
                        80,
                        8080,
                        8000,
                        5000,
                        8002
                    ]
            },
            {
                "type": "memcache",
                "ports":
                    [
                        11211
                    ]
            },
            {
                "type": "mysql",
                "ports":
                    [
                        3306,
                        3307
                    ]
            },
            {
                "type": "pgsql",
                "ports":
                    [
                        5432
                    ]
            },
            {
                "type": "redis",
                "ports":
                    [
                        6379
                    ]
            },
            {
                "type": "thrift",
                "ports":
                    [
                        9090
                    ]
            },
            {
                "type": "mongodb",
                "ports":
                    [
                        27017
                    ]
            },
            {
                "type": "nfs",
                "ports":
                    [
                        2049
                    ]
            },
            {
                "type": "tls",
                "ports":
                    [
                        443,
                        993,
                        995,
                        5223,
                        8443,
                        8883,
                        9243
                    ]
            },
            {
                "type": "sip",
                "ports":
                    [
                        5060
                    ]
            },
        ]},

        "parse_authorization": True,
        "parse_body": True,
        "keep_original": True,

        "packetbeat" : { "procs" : {"enabled": False}},
        "packetbeat" : { "ignore_outgoing": False },

        "output" : { "elasticsearch" :
        {
            "enabled": False,
            "hosts":
                [
                    "localhost:9200"
                ]
        }},

        "output" : { "logstash":
        {
            "enabled": True,
            "hosts":
                [
                    "${REMOTE_LOGSTASH_ADDRESS}:${REMOTE_LOGSTASH_PORT}"
                ],
            "index": "'packetbeat'"
        }},

        "setup" : { "template.settings": {} },
        "setup" : { "kibana": {} },
        "logging" : { "to_files": True },
        "logging" : { "files": {}}
    },

    "pcfconfigmap":
    {
        "logger":
            {
                "file": "/var/log/open5gs/pcf.log"
            },

        "db_uri": "mongodb://{{ include \"open5gs.fullname\" . }}-mongodb-svc/open5gs",

        "pcf":
            {
                "sbi":
                    [
                        {
                            "addr": "0.0.0.0",
                            "advertise": "{{ include \"open5gs.fullname\" . }}-pcf"
                        }
                    ]
            },
        "nrf":
            {
                "sbi":
                    {
                        "name": "{{ include \"open5gs.fullname\" . }}-nrf"
                    }
            }
    },

    "pcrfconfigmap":
    {
        "logger":
            {
                "level": "info"
            },
        "parameter": "",

        "pcrf":
            {
                "freeDiameter": "pcrf.conf"
            }
    },

    "sgwcconfigmap":
    {
        "logger":
            {
                "level": "info"
            },
        "parameter":
            {
                "no_ipv6": True
            },
        "max": {},
        "pool": {},

        "sgwc":
            {
                "gtpc":
                    {
                        "dev": "eth0"
                    },
                "pfcp":
                    {
                        "dev": "eth0"
                    }
            },

        "sgwu":
            {
                "pfcp":
                    [
                        {
                            "name": "\"{{ include \"open5gs.fullname\" . }}-sgwc\""
                        }
                    ]
            }
    },

    "sgwuconfigmap":
    {
        "logger":
            {
                "level": "info"
            },
        "parameter":
            {
                "no_ipv6": True
            },
        "max": {},
        "pool": {},

        "sgwu":
            {
                "gtpu":
                    {
                        "dev": "eth0"
                    },
                "pfcp":
                    {
                        "dev": "eth0"
                    }
            },

        "sgwc":
            {
                "pfcp":
                    [
                        {
                            "name": "\"{{ include \"open5gs.fullname\" . }}-sgwc\""
                        }
                    ]
            }
    },

    "smfconfigmap":
    {
        "logger":
            {
                "file": "/var/log/open5gs/smf.log"
            },
        "parameter":
            {
                "no_ipv6": True
            },
        "smf":
        {
            "sbi":
            [
                {
                    "addr": "0.0.0.0",
                    "advertise": "{{ include \"open5gs.fullname\" . }}-smf"
                }
            ],
            "pfcp":
            {
                "dev": "'{{ .Values.k8s.interface }}'"
            },
            "gtpc":
            {
                "dev": "'{{ .Values.k8s.interface }}'"
            },
            "gtpu":
            {
                "dev": "'{{ .Values.k8s.interface }}'"
            },
            "subnet":
            [
                {
                    "addr": "10.45.0.1/16",
                    "dnn": "'{{ .Values.dnn }}'"
                }
            ],
            "dns":
            [
                "8.8.8.8",
                "8.8.4.4"
            ],
            "mtu": "1400"
        },

        "nrf":
        {
            "sbi":
                {
                    "name": "{{ include \"open5gs.fullname\" . }}-nrf"
                }
        },

        "upf":
        {
            "pfcp":
                [
                    {
                        "name": "{{ include \"open5gs.fullname\" . }}-upf",
                        "dnn": "'{{ .Values.dnn }}'"
                    }
                ]
        }
    },

    "udmconfigmap":
    {
        "logger":
            {
                "file": "/var/log/open5gs/udm.log"
            },

        "udm":
            {
                "sbi":
                    [
                        {
                            "addr": "0.0.0.0",
                            "advertise": "{{ include \"open5gs.fullname\" . }}-udm"
                        }
                    ]
            },
        "nrf":
            {
                "sbi":
                    {
                        "name": "{{ include \"open5gs.fullname\" . }}-nrf"
                    }
            }
    },

    "udrconfigmap":
    {
        "logger":
            {
                "file": "/var/log/open5gs/udr.log"
            },

        "db_uri": "mongodb://{{ include \"open5gs.fullname\" . }}-mongodb-svc/open5gs",
        "udr":
            {
                "sbi":
                    [
                        {
                            "addr": "0.0.0.0",
                            "advertise": "{{ include \"open5gs.fullname\" . }}-udr"
                        }
                    ]
            },
        "nrf":
            {
                "sbi":
                    {
                        "name": "{{ include \"open5gs.fullname\" . }}-nrf"
                    }
            }
    },

    "upfconfigmap":
    {
        "logger":
            {
                "file": "/var/log/open5gs/upf.log"
            },

        "upf":
            {
                "pfcp":
                    {
                        "dev": "'{{ .Values.k8s.interface }}'"
                    },
                "gtpu":
                    {
                        "dev": "'{{ .Values.k8s.interface }}'"
                    },
                "subnet":
                    [
                        {
                            "addr": "10.45.0.1/16",
                            "dnn": '{{ .Values.dnn }}'
                        }
                    ]
            }
    },

    "subscribers":
    [
        {
            "imsi": "901700000017408",
            "k": "B1233463AB9BC2AD2DB1830EB6417E7B",
            "opc": "625150E2A943E3353DD23554101CAFD4"
        },
        {
            "imsi": "310789012345301",
            "k": "82E9053A1882085FF2C020359938DAE9",
            "opc": "BFD5771AAF4F6728E9BC6EF2C2533BDB"
        }
    ]
}
