from pymongo.synchronous.database import Database

from nfvcl_core.migrations import Migration
from nfvcl_core.utils.log import create_logger


class Migration001Initial(Migration):
    def __init__(self):
        self.logger = create_logger("Migration001Initial")

    def upgrade(self, db: Database):
        self.logger.info("Test migration upgrade")
        collection = db['topology'].find() # There is only ONE 'topology' collection in the database

        for topology_item in collection:
            k8s_list = topology_item['kubernetes']
            for k8s_item in k8s_list:
                if not k8s_item['provided_by'] == 'NFVCL':
                    k8s_item['provided_by'] = 'EXTERNAL'


            db['topology'].update_one({"_id": topology_item["_id"]}, {"$set": {"kubernetes": k8s_list}})


    def downgrade(self, db: Database):
        pass
