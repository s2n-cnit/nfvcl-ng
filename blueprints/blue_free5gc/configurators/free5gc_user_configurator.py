from pymongo import MongoClient
from bson import ObjectId
from main import *

# create logger
logger = create_logger('Configurator_Free5GC_User')

class Configurator_Free5GC_User():
    def __init__(self) -> None:
        pass

    def add_ue_to_db(self, plmn: str, imsi: str, key: str, ocv: str, defaultUeUplink: str = "10 Mbps",
                     defaultUeDownlink: str = "20 Mbps", gpsis: str = "msisdn-0900000000",
                     mongodbServiceHost: str = "mongodb://mongodb:27017/") -> None:
        client = MongoClient(mongodbServiceHost)
        db = client["free5gc"]

        response = db.policyData.ues.amData.update(
            {
                "ueId" : "imsi-{}".format(imsi)
            },
            {
                "$setOnInsert": {
                        "_id": ObjectId(),
                        "ueId": "imsi-{}".format(imsi),
                        "subscCats": ["free5gc"]
                }
            },
            upsert = True
        )
        logger.info("db response: {}".format(response))

        response = db.policyData.ues.smData.update(
            {
                "ueId" : "imsi-{}".format(imsi)
            },
            {
                "$setOnInsert": {
                    "_id": ObjectId(),
                    "ueId": "imsi-{}".format(imsi)
                }
            },
            upsert = True
        )
        logger.info("db response: {}".format(response))

        response = db.subscriptionData.authenticationData.authenticationSubscription.update(
            {
                "ueId" : "imsi-{}".format(imsi)
            },
            {
                "$setOnInsert": {
                        "_id": ObjectId()
                },
                "$set": {
                        "ueId": "imsi-{}".format(imsi),
                        "authenticationMethod":"5G_AKA",
                        "permanentKey": {
                            "permanentKeyValue": format(key),
                            "encryptionKey": 0,
                            "encryptionAlgorithm":0
                        },
                        "sequenceNumber": "16f3b3f70fc2",
                        "authenticationManagementField": "8000",
                        "milenage": {
                            "op": {
                                "opValue": "",
                                "encryptionKey": 0,
                                "encryptionAlgorithm": 0
                            }
                        },
                        "opc": {
                            "opcValue": format(ocv),
                            "encryptionKey": 0,
                            "encryptionAlgorithm": 0
                        }
                    }
            },
            upsert = True
        )
        logger.info("db response: {}".format(response))

        db.subscriptionData.provisionedData.amData.update(
            {
                "ueId" : "imsi-{}".format(imsi)
            },
            {
                "$setOnInsert": {
                        "_id": ObjectId()
                },
                "$set": {
                        "ueId": "imsi-{}".format(imsi),
                        "gpsis": [
                            format(gpsis)
                        ],
                        "subscribedUeAmbr": {
                            "uplink": format(defaultUeUplink),
                            "downlink": format(defaultUeDownlink)
                        },
                        "nssai": {
                            "defaultSingleNssais": []
                        },
                        "servingPlmnId": format(plmn)
                    }
            },
            upsert = True
        )
        logger.info("db response: {}".format(response))

        response = db.subscriptionData.provisionedData.smfSelectionSubscriptionData.update(
            {
                "ueId" : "imsi-{}".format(imsi)
            },
            {
                "$setOnInsert": {
                        "_id": ObjectId()
                },
                "$set": {
                        "ueId": "imsi-{}".format(imsi),
                        "servingPlmnId": format(plmn)
                    }
            },
            upsert = True
        )
        logger.info("db response: {}".format(response))

    def del_ue_from_db(self, plmn: str, imsi: str,
                     mongodbServiceHost: str = "mongodb://mongodb:27017/") -> None:
        client = MongoClient(mongodbServiceHost)
        db = client["free5gc"]

        response = db.policyData.ues.amData.delete_many(
            {
                "ueId" : "imsi-{}".format(imsi)
            }
        )
        logger.info("db response: {}".format(response.deleted_count))

        response = db.policyData.ues.smData.delete_many(
            {
                "ueId" : "imsi-{}".format(imsi)
            }
        )
        logger.info("db response: {}".format(response.deleted_count))

        response = db.subscriptionData.authenticationData.authenticationSubscription.delete_many(
            {
                "ueId" : "imsi-{}".format(imsi)
            }
        )
        logger.info("db response: {}".format(response.deleted_count))

        db.subscriptionData.provisionedData.amData.delete_many(
            {
                "ueId" : "imsi-{}".format(imsi)
            }
        )
        logger.info("db response: {}".format(response.deleted_count))

        db.subscriptionData.provisionedData.smData.delete_many(
            {
                "ueId" : "imsi-{}".format(imsi)
            }
        )
        logger.info("db response: {}".format(response.deleted_count))

        response = db.subscriptionData.provisionedData.smfSelectionSubscriptionData.delete_many(
            {
                "ueId" : "imsi-{}".format(imsi)
            }
        )
        logger.info("db response: {}".format(response.deleted_count))

    def add_snssai_to_db(self, plmn: str, imsi: str, sst: str, sd: str, default: bool = True,
                     mongodbServiceHost: str = "mongodb://mongodb:27017/") -> None:
        client = MongoClient(mongodbServiceHost)
        db = client["free5gc"]

        nssaiType = "singleNssais"
        if default:
            nssaiType = "defaultSingleNssais"

        response = db.policyData.ues.smData.update(
            {
                "ueId": "imsi-{}".format(imsi)
            },
            {
                "$set": {
                    "smPolicySnssaiData.{:02x}{}".format(sst, sd):
                        {
                            "snssai": {
                                "sst": int(sst), "sd": format(sd)
                                }
                        }
                }
            },
            upsert=True
        )
        logger.info("db response: {}".format(response))

        response = db.subscriptionData.provisionedData.amData.update(
            {
                "ueId": "imsi-{}".format(imsi)
            },
            {
                "$push": {
                    "nssai.{}".format(nssaiType):
                        {
                            "sst": int(sst), "sd": format(sd)
                        }
                }
            },
            upsert=True
        )
        logger.info("db response: {}".format(response))

        response = db.subscriptionData.provisionedData.smData.update(
            {
                "ueId": "imsi-{}".format(imsi),
                "singleNssai": {
                    "sst": format(sst),"sd": format(sd)
                }
            },
            {
                "$setOnInsert": {
                        "_id": ObjectId()
                },
                "$set": {
                        "singleNssai": {"sst": int(sst),"sd": format(sd)},
                        "ueId":"imsi-{}".format(imsi),
                        "servingPlmnId": format(plmn)
                    }
            },
            upsert=True
        )
        logger.info("db response: {}".format(response))

    def add_dnn_to_db(self, imsi: str, sst: str, sd: str, dnn: str, d5qi: int, upambr: str, downambr: str,
                     mongodbServiceHost: str = "mongodb://mongodb:27017/") -> None:
        client = MongoClient(mongodbServiceHost)
        db = client["free5gc"]

        response = db.policyData.ues.smData.update(
            {
                "ueId": "imsi-{}".format(imsi)
            },
            {
                "$set": {
                    "smPolicySnssaiData.{:02x}{}.smPolicyDnnData.{}".format(sst, sd, dnn): {"dnn": format(dnn)}
                }
            },
            upsert=True
        )
        logger.info("db response: {}".format(response))

        response = db.subscriptionData.provisionedData.smData.update(
            {
                "ueId": "imsi-{}".format(imsi),
                "singleNssai": {
                    "sst": int(sst),"sd": format(sd)
                }
            },
            {
                "$set": {
                        "dnnConfigurations": {
                            format(dnn): {
                                "sscModes": {
                                    "defaultSscMode": "SSC_MODE_1",
                                    "allowedSscModes": ["SSC_MODE_2","SSC_MODE_3"]
                                },
                                "5gQosProfile": {
                                    "5qi": d5qi,
                                    "arp": {
                                        "priorityLevel": 8,
                                        "preemptCap": "",
                                        "preemptVuln": ""
                                    },
                                    "priorityLevel": 8
                                 },
                                 "sessionAmbr": {
                                        "downlink": format(downambr),
                                        "uplink": format(upambr)
                                 },
                                 "pduSessionTypes": {
                                        "defaultSessionType":"IPV4",
                                        "allowedSessionTypes":["IPV4"]
                                 }
                            }
                        }
                    }
            },
            upsert=True
        )
        logger.info("db response: {}".format(response))

        response = db.subscriptionData.provisionedData.smfSelectionSubscriptionData.update(
            {
                "ueId": "imsi-{}".format(imsi)
            },
            {
                "$push": {
                        "subscribedSnssaiInfos.{:02x}{}.dnnInfos".format(sst, sd): {"dnn": format(dnn)}
                    }
            },
            upsert=True
        )
        logger.info("db response: {}".format(response))

    def add_ues(self, msg: dict):
        mongoDbPath = None
        if "config" in msg:
            if "mongodb" in msg["config"]:
                mongoDbPath = "mongodb://{}:27017/".format(msg["config"]["mongodb"])

        if "config" in msg and "plmn" in msg["config"]:
            if "subscribers" in msg["config"]:
                for subscriber in msg["config"]["subscribers"]:
                    plmn = msg["config"]["plmn"]
                    imsi = subscriber["imsi"]
                    if "k" in subscriber and "opc" in subscriber:
                        key = subscriber["k"]
                        opc = subscriber["opc"]

                        self.add_ue_to_db(plmn=plmn, imsi=imsi, key=key, ocv=opc,
                                                      mongodbServiceHost=mongoDbPath)

                    if "snssai" in subscriber:
                        for snssaiElem in subscriber["snssai"]:
                            sst = snssaiElem["sst"]  # TODO "sliceId" in the json
                            sd = snssaiElem["sd"]  # TODO "sliceType" in the json
                            default = snssaiElem["default"]

                            self.add_snssai_to_db(plmn=plmn, imsi=imsi, sst=sst, sd=sd, default=default,
                                                              mongodbServiceHost=mongoDbPath)

                            if "dnnList" in snssaiElem:
                                for dnnElem in snssaiElem["dnnList"]:
                                    dnn = dnnElem["dnn"]
                                    uplinkAmbr = dnnElem["uplinkAmbr"]
                                    downlinkAmbr = dnnElem["downlinkAmbr"]
                                    default5qi = dnnElem["default5qi"]

                                    self.add_dnn_to_db(imsi=imsi, sst=sst, sd=sd, dnn=dnn, d5qi=default5qi,
                                                                   upambr=uplinkAmbr, downambr=downlinkAmbr,
                                                                   mongodbServiceHost=mongoDbPath)

                                    # TODO complete with flowRules

    def del_ues(self, msg: dict):
        mongoDbPath = None
        if "config" in msg:
            if "mongodb" in msg["config"]:
                mongoDbPath = "mongodb://{}:27017/".format(msg["config"]["mongodb"])

        if "config" in msg and "plmn" in msg["config"]:
            if "subscribers" in msg["config"]:
                for subscriber in msg["config"]["subscribers"]:
                    plmn = msg["config"]["plmn"]
                    imsi = subscriber["imsi"]
                    self.del_ue_from_db(plmn=plmn, imsi=imsi, mongodbServiceHost=mongoDbPath)
