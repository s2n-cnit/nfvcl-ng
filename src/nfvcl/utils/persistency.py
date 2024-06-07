from pymongo import MongoClient
from nfvcl.models.config_model import NFVCLConfigModel
from nfvcl.utils.util import get_nfvcl_config
nfvcl_config: NFVCLConfigModel = get_nfvcl_config()


mongo_client: MongoClient = MongoClient("mongodb://{}:{}/".format(nfvcl_config.mongodb.host, nfvcl_config.mongodb.port))
OSSdb = mongo_client[nfvcl_config.mongodb.db]

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
    def find_DB(collection, data, exclude=None):
        if exclude is None:
            exclude = {'_id': False}
        db = OSSdb[collection]
        return db.find(data, projection=exclude)

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


