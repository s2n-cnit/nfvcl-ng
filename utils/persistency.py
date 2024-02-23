import json
from typing import List, Any, Mapping

from pymongo import MongoClient
from pymongo.cursor import Cursor

from models.config_model import NFVCLConfigModel
from utils.util import get_nfvcl_config
nfvcl_config: NFVCLConfigModel = get_nfvcl_config()


mongo_client: MongoClient = MongoClient("mongodb://{}:{}/".format(nfvcl_config.mongodb.host, nfvcl_config.mongodb.port))
OSSdb = mongo_client[nfvcl_config.mongodb.db]

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

BLUE_COLLECTION_V2 = "blue-inst-v2"


class db_management:
    def backup_DB(self):
        # TODO make possible to backupdb from APIs
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

nfvcl_database: DB | None = None

def _get_database():
    global nfvcl_database
    if nfvcl_database is None:
        nfvcl_database = DB()
    return nfvcl_database


def get_ng_blue_by_id_filter(blueprint_id: str) -> dict | None:
    blue_list = _get_database().find_DB(BLUE_COLLECTION_V2, {'id': blueprint_id})
    for blue in blue_list:
        return blue # Return the first match
    return None

def get_ng_blue_list(blueprint_type: str = None) -> List[dict]:
    blue_filter = {}
    if blueprint_type:
        blue_filter = {'type': type}
    blue_list = _get_database().find_DB(BLUE_COLLECTION_V2, blue_filter)
    return list(blue_list)

def get_cursor_ng_by_id_filter(blueprint_id: str) -> Cursor[dict]:
    return _get_database().find_DB(BLUE_COLLECTION_V2, {'id': blueprint_id})


def save_ng_blue(blueprint_id: str, dict_blue: dict):
    database_instance = _get_database()
    if database_instance.exists_DB(BLUE_COLLECTION_V2, {'id': blueprint_id}):
        return database_instance.update_DB(BLUE_COLLECTION_V2, dict_blue,{'id': blueprint_id})
    else:
        return database_instance.insert_DB(BLUE_COLLECTION_V2, dict_blue)

def destroy_ng_blue(blueprint_id: str):
    return _get_database().delete_DB(BLUE_COLLECTION_V2, {'id': blueprint_id})
