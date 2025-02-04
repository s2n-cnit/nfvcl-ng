from typing import List

from pymongo.synchronous.database import Database

from nfvcl.models.k8s.topology_k8s_model import K8sNetworkInfo
from nfvcl_core.migrations import Migration
from nfvcl_core.utils.log import create_logger


class Migration003K8sNetwork(Migration):
    def __init__(self):
        self.logger = create_logger("Migration003K8sNetwork")

    def upgrade(self, db: Database):
        collection = db['topology'].find() # There is only ONE 'topology' collection in the database

        for topology_item in collection:
            k8s_list = topology_item['kubernetes']
            for k8s_item in k8s_list:
                if "multus_info" in k8s_item:
                    del k8s_item["multus_info"]
                if "networks" in k8s_item:
                    new_network_list: List[K8sNetworkInfo] = []
                    for network in k8s_item["networks"]:
                        new_network_list.append(K8sNetworkInfo(name=network))
                    k8s_item["networks"] = [item.model_dump(exclude_none=True) for item in new_network_list]
            db['topology'].update_one({"_id": topology_item["_id"]}, {"$set": {"kubernetes": k8s_list}})


    def downgrade(self, db: Database):
        pass
