import json
from pymongo import MongoClient

from models.config_model import NFVCLConfigModel
from utils.util import get_nfvcl_config

nfvcl_config: NFVCLConfigModel = get_nfvcl_config()


persLayer = MongoClient("mongodb://{}:{}/".format(nfvcl_config.mongodb.host, nfvcl_config.mongodb.port))
OSSdb = persLayer[nfvcl_config.mongodb.db]

persistent_collections = [
    "blueprints",
    "license",
    "nsd_templates",
    "nsd_templates_sol006",
    "pdu",
    "plmn",
    "pnf",
    "ue"
]

volatile_collections = [
    "action_output",
    "blueprint-instances",
    "blueprint_slice_intent",
    "ip_addresses",
    "nfv_performance",
    "osm_status",
    "vnfi"
]


class db_management:
    def backup_DB(self):
        data = {}
        for c in persistent_collections:
            data[c] = []
            db = OSSdb[c]
            cursor = db.find({})
            for document in cursor:
                document.pop("_id")
                data[c].append(document)

        with open('../db_backup.json', 'w') as file:
            json.dump(data, file)
        # print(data)

    def install_DB(self):
        # create all the collections
        for c in persistent_collections + volatile_collections:
            print(c)
        with open('../db_backup.json', 'r') as file:
            data = json.load(file)
        for collection in data:
            print(data[collection])

    def clean_volatile(self):
        pass


class DB:
    @staticmethod
    def insert_DB(collection, data):
        db = OSSdb[collection]
        return db.insert_one(data)

    @staticmethod
    def exists_DB(collection, data):
        db = OSSdb[collection]
        #return db.find(data).count() >= 1
        return db.count_documents(data) > 0

    @staticmethod
    def find_DB(collection, data):
        db = OSSdb[collection]
        return db.find(data)

    @staticmethod
    def findone_DB(collection, data):
        db = OSSdb[collection]
        return db.find_one(data)

    @staticmethod
    def update_DB(table, data, filter):
        db = OSSdb[table]
        # for i in db.find(filter):
        db.update_one(filter, {"$set": data}, upsert=True)

    @staticmethod
    def delete_DB(table, filter):
        db = OSSdb[table]
        return db.delete_many(filter)
