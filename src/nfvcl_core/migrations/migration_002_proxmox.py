from pymongo.synchronous.database import Database

from nfvcl_core.migrations.base_class_migration import Migration
from nfvcl_common.utils.log import create_logger


class Migration002Proxmox(Migration):
    def __init__(self):
        self.logger = create_logger("Migration002Proxmox")

    def upgrade(self, db: Database):
        collection = db['topology'].find()

        for topology_item in collection:
            vims_list = topology_item['vims']
            for vim_item in vims_list:
                if "vim_proxmox_storage_id" in vim_item.keys():
                    vim_item['vim_proxmox_images_volume'] = vim_item['vim_proxmox_storage_id']
                    del vim_item['vim_proxmox_storage_id']
                if "vim_proxmox_storage_volume" in vim_item.keys():
                    vim_item['vim_proxmox_vm_volume'] = vim_item['vim_proxmox_storage_volume']
                    del vim_item['vim_proxmox_storage_volume']

            db['topology'].update_one({"_id": topology_item["_id"]}, {"$set": {"vims": vims_list}})



    def downgrade(self, db: Database):
        pass
