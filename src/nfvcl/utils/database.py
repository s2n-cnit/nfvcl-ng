import json
from pathlib import Path
from typing import List
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.results import InsertOneResult
from nfvcl.models.config_model import NFVCLConfigModel
from nfvcl.utils.patterns import Singleton
from nfvcl.utils.util import get_nfvcl_config

nfvcl_config: NFVCLConfigModel = get_nfvcl_config()

NFVCL_DB_BACKUP_PATH: Path = Path("db_backup.json")
BLUE_COLLECTION_V2 = "blue-inst-v2"
TOPOLOGY_COLLECTION = "topology"
EXTRA_COLLECTION = "extra"


class NFVCLDatabase(object, metaclass=Singleton):
    mongo_client: MongoClient
    mongo_database: Database

    def __init__(self):
        if nfvcl_config.mongodb.username is not None and nfvcl_config.mongodb.password is not None:
            uri = f"mongodb://{nfvcl_config.mongodb.username}:{nfvcl_config.mongodb.password}@{nfvcl_config.mongodb.host}:{nfvcl_config.mongodb.port}/"
        else:
            uri = f"mongodb://{nfvcl_config.mongodb.host}:{nfvcl_config.mongodb.port}/"
        self.mongo_client: MongoClient = MongoClient(uri)
        self.mongo_database = self.mongo_client[nfvcl_config.mongodb.db]
        self.test_connection()

    def test_connection(self):
        self.list_collections()

    def list_collections(self):
        return self.mongo_database.list_collections()

    def insert_in_collection(self, collection_name: str, data: dict) -> InsertOneResult:
        collection = self.mongo_database[collection_name]
        return collection.insert_one(data)

    def find_collection(self, collection, data, exclude=None):
        if exclude is None:
            exclude = {}

        collection = self.mongo_database[collection]
        return collection.find(data, exclude)

    def find_in_collection(self, collection, data, exclude=None):
        if exclude is None:
            exclude = {}
        # dictionary specifying the query to be performed
        collection = self.mongo_database[collection]
        return collection.find(data, exclude)

    def find_one_in_collection(self, collection, data, exclude=None):
        if exclude is None:
            exclude = {}
        # dictionary specifying the query to be performed
        collection = self.mongo_database[collection]
        return collection.find_one(data, exclude)

    def exists_in_collection(self, collection, data):
        collection = self.mongo_database[collection]

        return collection.count_documents(data) > 0

    def update_in_collection(self, collection, data, filter):
        db = self.mongo_database[collection]
        # for i in db.find(filter):
        db.update_one(filter, {"$set": data}, upsert=True)

    def delete_from_collection(self, collection, filter):
        db = self.mongo_database[collection]
        return db.delete_many(filter)

    def backup_locally(self):
        local_database = {}

        for collection_info in self.mongo_database.list_collections():
            db_collection = self.mongo_database[collection_info['name']]
            local_database[collection_info['name']] = []
            for item in db_collection.find():
                item.pop('_id', None)
                local_database[collection_info['name']].append(item)

        local_file = NFVCL_DB_BACKUP_PATH
        with local_file.open('w') as local_file_opened:
            json.dump(local_database, local_file_opened)


def get_ng_blue_list(blueprint_type: str = None) -> List[dict]:
    """
    Retrieve all blueprints from the database.
    Args:
        blueprint_type: The optional filter to be used to filter results.

    Returns:
        The filtered blueprint list.
    """
    blue_filter = {}
    if blueprint_type:
        blue_filter = {'type': blueprint_type}
    blue_list = NFVCLDatabase().find_collection(BLUE_COLLECTION_V2, blue_filter, {"_id": False})
    return list(blue_list)


def get_ng_blue_by_id_filter(blueprint_id: str) -> dict | None:
    """
    Retrieve a blueprint from the database, given the blueprint ID.

    Args:
        blueprint_id: The blueprint ID

    Returns:
        The FIRST MATCH of blueprint (dict) if found, None otherwise.
    """
    blue_list = NFVCLDatabase().find_in_collection(BLUE_COLLECTION_V2, {'id': blueprint_id}, {"_id": False})
    for blue in blue_list:
        return blue  # Return the first match
    return None


def save_ng_blue(blueprint_id: str, dict_blue: dict):
    """
    Save a blueprint to the database. IF already existing it updates the object, otherwise it creates a new one.

    Args:
        blueprint_id: The blueprint ID, used to look for blueprints in the database.
        dict_blue: The object to be saved/updated.

    Returns:
        The result of the operation (saved object)
    """
    database_instance = NFVCLDatabase()
    if database_instance.exists_in_collection(BLUE_COLLECTION_V2, {'id': blueprint_id}):
        return database_instance.update_in_collection(BLUE_COLLECTION_V2, dict_blue, {'id': blueprint_id})
    else:
        return database_instance.insert_in_collection(BLUE_COLLECTION_V2, dict_blue)


def destroy_ng_blue(blueprint_id: str):
    """
    Destroy a blueprint in the database if it exists.
    Args:
        blueprint_id: The blueprint ID

    Returns:
        The destroyed blueprint.
    """
    return NFVCLDatabase().delete_from_collection(BLUE_COLLECTION_V2, {'id': blueprint_id})


def save_topology(dict_topo: dict):
    """
    Save a blueprint to the database. If it is already existing, it updates the object, otherwise it creates a new one.

    Args:
        dict_topo: The dict of topology to be saved.

    Returns:
        The result of the operation (saved object)
    """
    database_instance = NFVCLDatabase()
    if database_instance.exists_in_collection(TOPOLOGY_COLLECTION, {'id': 'topology'}):  # TOPO is unique, fixed ID
        return database_instance.update_in_collection(TOPOLOGY_COLLECTION, dict_topo, {'id': 'topology'})
    else:
        return database_instance.insert_in_collection(TOPOLOGY_COLLECTION, dict_topo)


def delete_topology():
    """
    Destroy the topology in the database if it exists.

    Returns:
        The destroyed topology.
    """
    return NFVCLDatabase().delete_from_collection(TOPOLOGY_COLLECTION, {'id': 'topology'})

def insert_extra(object_id: str, object_dict: dict):
    """
    Insert in the 'extra' collection an object with the given id. Used in cases where extra functionalities require
    extra data that is not strictly related to NFVCL.

    Args:
        object_id: The id used to identify the object.
        object_dict: The dictionary to be inserted into the 'extra' collection.

    Returns:

    """
    database_instance = NFVCLDatabase()
    object_dict['id'] = object_id
    if database_instance.exists_in_collection(EXTRA_COLLECTION, {'id': object_id}):
        return database_instance.update_in_collection(EXTRA_COLLECTION, object_dict, {'id': object_id})
    else:
        return database_instance.insert_in_collection(EXTRA_COLLECTION, object_dict)

def get_extra(object_id: str) -> dict | None:
    """
    Insert in the 'extra' collection an object with the given id. Used in cases where extra functionalities require
    extra data that is not strictly related to NFVCL.

    Args:
        object_id: The id used to identify the object.
        object_dict: The dictionary to be inserted into the 'extra' collection.

    Returns:

    """
    extra_list = NFVCLDatabase().find_in_collection(EXTRA_COLLECTION, {'id': object_id}, {"_id": False})
    for extra in extra_list:
        return extra  # Return the first match
    return None
