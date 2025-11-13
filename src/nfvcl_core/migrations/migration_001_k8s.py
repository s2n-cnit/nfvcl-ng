from typing import List

from pymongo.synchronous.database import Database

from nfvcl_core_models.topology_k8s_model import K8sNetworkInfo
from nfvcl_core.migrations.base_class_migration import Migration
from nfvcl_common.utils.log import create_logger


class Migration003K8s(Migration):
    def __init__(self):
        self.logger = create_logger("Migration001K8s")

    def upgrade(self, db: Database):
        collection = db['topology'].find() # There is only ONE 'topology' collection in the database

        for topology_item in collection:
            k8s_list = topology_item['kubernetes']
            for k8s_item in k8s_list:
                if not k8s_item['provided_by'] == 'NFVCL':
                    k8s_item['provided_by'] = 'EXTERNAL'
                if "multus_info" in k8s_item:
                    del k8s_item["multus_info"]
                if "networks" in k8s_item:
                    new_network_list: List[K8sNetworkInfo] = []
                    for network in k8s_item["networks"]:
                        if isinstance(network, str):
                            new_network_list.append(K8sNetworkInfo(name=network))
                        else:
                            new_network_list.append(K8sNetworkInfo(**network))
                    k8s_item["networks"] = [item.model_dump(exclude_none=True) for item in new_network_list]

            db['topology'].update_one({"_id": topology_item["_id"]}, {"$set": {"kubernetes": k8s_list}})

            network_list = topology_item['networks']
            for network in network_list:
                if "allocation_pool" in network:
                    for all_pool in network["allocation_pool"]:
                        if "used" in all_pool:
                            del all_pool["used"]

            db['topology'].update_one({"_id": topology_item["_id"]}, {"$set": {"networks": network_list}})


    def downgrade(self, db: Database):
        pass
