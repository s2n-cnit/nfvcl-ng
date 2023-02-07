from pymongo import MongoClient
from bson import ObjectId
from enum import Enum
from blueprints.blue_free5gc.configurators.free5gc_core_configurator import SstConvertion
from main import *

# create logger
logger = create_logger('Configurator_Free5GC_User')

class UpSecurityType(Enum):
    PREFERRED = 0
    NOT_NEEDED = 1
    REQUIRED = 2

class Configurator_Free5GC_User():
    def __init__(self) -> None:
        pass

    def add_ue_to_db(self, plmn: str, imsi: str, key: str, ocv: str, defaultUeUplink: str = "1 Gbps",
                     defaultUeDownlink: str = "2 Gbps", gpsis: str = "msisdn-0900000000",
                     mongodbServiceHost: str = "mongodb://mongodb:27017/") -> None:
        client = MongoClient(mongodbServiceHost)
        db = client["free5gc"]

        response = db.policyData.ues.amData.update_many(
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
        logger.info("db response: {}".format(response.raw_result))

        response = db.policyData.ues.smData.update_many(
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
        logger.info("db response: {}".format(response.raw_result))

        response = db.subscriptionData.authenticationData.authenticationSubscription.update_many(
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
        logger.info("db response: {}".format(response.raw_result))

        response = db.subscriptionData.provisionedData.amData.update_many(
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
        logger.info("db response: {}".format(response.raw_result))

        response = db.subscriptionData.provisionedData.smfSelectionSubscriptionData.update_many(
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
        logger.info("db response: {}".format(response.raw_result))

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

        response = db.policyData.ues.flowRule.delete_many(
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

    def add_snssai_to_db(self, plmn: str, imsi: str, sst: int, sd: str, default: bool = True,
                     mongodbServiceHost: str = "mongodb://mongodb:27017/") -> None:
        client = MongoClient(mongodbServiceHost)
        db = client["free5gc"]

        nssaiType = "singleNssais"
        if default:
            nssaiType = "defaultSingleNssais"

        response = db.policyData.ues.smData.update_many(
            {
                "ueId": "imsi-{}".format(imsi)
            },
            {
                "$set": {
                    "smPolicySnssaiData.{:02x}{}".format(sst, sd):
                        {
                            "snssai": {
                                "sst": sst, "sd": format(sd)
                                }
                        }
                }
            },
            upsert=True
        )
        logger.info("db response: {}".format(response.raw_result))

        response = db.subscriptionData.provisionedData.amData.update_many(
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
        logger.info("db response: {}".format(response.raw_result))

        response = db.subscriptionData.provisionedData.smData.update_many(
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
        logger.info("db response: {}".format(response.raw_result))

    def add_dnn_to_db(self, imsi: str, sst: int, sd: str, dnn: str, d5qi: int, upambr: str, downambr: str,
                     mongodbServiceHost: str = "mongodb://mongodb:27017/") -> None:
        client = MongoClient(mongodbServiceHost)
        db = client["free5gc"]

        response = db.policyData.ues.smData.update_many(
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
        logger.info("db response: {}".format(response.raw_result))

        response = db.subscriptionData.provisionedData.smData.update_many(
            {
                "ueId": "imsi-{}".format(imsi),
                "singleNssai": {
                    "sst": sst,"sd": format(sd)
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
        logger.info("db response: {}".format(response.raw_result))

        response = db.subscriptionData.provisionedData.smfSelectionSubscriptionData.update_many(
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
        logger.info("db response: {}".format(response.raw_result))

    def add_flow_to_db(self, gbrUL: str, gbrDL: str, imsi: str, servingPlmnId: str, dnn: str, fiveqi: str,
                     mbrUL: str, filter: str, snssai: str, mbrDL: str,
                     mongodbServiceHost: str = "mongodb://mongodb:27017/") -> None:
        client = MongoClient(mongodbServiceHost)
        db = client["free5gc"]

        response = db.policyData.ues.flowRule.update_many(
            {
                "ueId" : "imsi-{}".format(imsi)
            },
            {
                "$setOnInsert": {
                        "_id": ObjectId(),
                        "ueId": "imsi-{}".format(imsi)
                },
                "$set": {
                        "gbrUL": gbrUL,
                        "gbrDL": gbrDL,
                        "servingPlmnId": servingPlmnId,
                        "dnn": dnn,
                        "5qi": float(fiveqi),
                        "mbrUL": mbrUL,
                        "filter": filter,
                        "snssai": snssai,
                        "mbrDL": mbrDL
                }
            },
            upsert = True
        )
        logger.info("db response: {}".format(response.raw_result))

    # def add_up_security_to_db(self, imsi: str, sst: int, sd: int, dnn: str,
    #                           integrity: UpSecurityType = UpSecurityType.NOT_NEEDED,
    #                           confidentiality: UpSecurityType = UpSecurityType.NOT_NEEDED,
    #                           mongodbServiceHost: str = "mongodb://mongodb:27017/") -> None:
    #     client = MongoClient(mongodbServiceHost)
    #     db = client["free5gc"]
    #
    #     response = db.policyData.ues.flowRule.update_many(
    #         {
    #             "ueId": "imsi-{}".format(imsi),
    #             "singleNssai": {
    #                 "sst": sst,"sd": format(sd)
    #             },
    #             "dnnConfigurations"
    #         },
    #         {
    #             "$setOnInsert": {
    #                     "_id": ObjectId(),
    #                     "gbrUL": gbrUL,
    #                     "gbrDL": gbrDL,
    #                     "ueId": "imsi-{}".format(imsi),
    #                     "servingPlmnId": servingPlmnId,
    #                     "dnn": dnn,
    #                     "5qi": int(fiveqi),
    #                     "mbrUL": mbrUL,
    #                     "filter": filter,
    #                     "snssai": snssai,
    #                     "mbrDL": mbrDL
    #             }
    #         },
    #         upsert = True
    #     )
    #     logger.info("db response: {}".format(response))


    def add_ues(self, msg: dict) -> None:
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
                            sst = SstConvertion.to_int(snssaiElem["sliceType"])
                            sd = snssaiElem["sliceId"]
                            default = snssaiElem["default_slice"]

                            self.add_snssai_to_db(plmn=plmn, imsi=imsi, sst=sst, sd=sd, default=default,
                                                              mongodbServiceHost=mongoDbPath)

                            if "sliceProfiles" in msg["config"]:
                                for sliceProfile in msg["config"]["sliceProfiles"]:
                                    if sliceProfile["sliceId"] == snssaiElem["sliceId"] \
                                            and sliceProfile["sliceType"] == snssaiElem["sliceType"]:
                                        if "dnnList" in sliceProfile:
                                            if "network_endpoints" in msg["config"] \
                                                    and "data_nets" in msg["config"]["network_endpoints"]:
                                                for net_name in sliceProfile["dnnList"]:
                                                    for data_net in msg["config"]["network_endpoints"]["data_nets"]:
                                                        if net_name == data_net["net_name"]:
                                                            dnn = data_net["dnn"]
                                                            uplinkAmbr = data_net["uplinkAmbr"]
                                                            downlinkAmbr = data_net["downlinkAmbr"]
                                                            default5qi = data_net["default5qi"]

                                                            self.add_dnn_to_db(imsi=imsi, sst=sst, sd=sd, dnn=dnn,
                                                                    d5qi=int(default5qi),upambr=uplinkAmbr,
                                                                    downambr=downlinkAmbr, mongodbServiceHost=mongoDbPath)
                                    if "profileParams" in sliceProfile and "pduSessions" in sliceProfile["profileParams"]:
                                        if "pduSessionIds" in snssaiElem:
                                            for pduSessionId in snssaiElem["pduSessionIds"]:
                                                for pduSession in sliceProfile["profileParams"]["pduSessions"]:
                                                    if pduSessionId == pduSession["pduSessionId"]:
                                                        for flow in pduSession["flows"]:
                                                            gbrUL = flow["gfbr"]
                                                            gbrDL = flow["gfbr"]
                                                            #imsi = imsi
                                                            servingPlmnId = plmn
                                                            fiveqi = flow["qi"]
                                                            mbrUL = flow["gfbr"]
                                                            filter = flow["ipAddrFilter"]
                                                            snssai = "{:02x}{}".format(sst, sd)
                                                            mbrDL = flow["gfbr"]
                                                            for dnn in sliceProfile["dnnList"]:
                                                                self.add_flow_to_db(gbrUL, gbrDL, imsi, servingPlmnId,
                                                                                    dnn, fiveqi, mbrUL, filter, snssai,
                                                                                    mbrDL,mongodbServiceHost=mongoDbPath)

    def del_ues(self, msg: dict) -> None:
        mongoDbPath = None
        if "config" in msg:
            if "mongodb" in msg["config"]:
                mongoDbPath = "mongodb://{}:27017/".format(msg["config"]["mongodb"])

            if "plmn" in msg["config"]:
                if "subscribers" in msg["config"]:
                    for subscriber in msg["config"]["subscribers"]:
                        plmn = msg["config"]["plmn"]
                        imsi = subscriber["imsi"]
                        self.del_ue_from_db(plmn=plmn, imsi=imsi, mongodbServiceHost=mongoDbPath)
