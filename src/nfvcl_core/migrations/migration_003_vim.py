from pymongo.synchronous.database import Database

from nfvcl_core.migrations.base_class_migration import Migration
from nfvcl_core.utils.log import create_logger


class Migration002Proxmox(Migration):
    def __init__(self):
        self.logger = create_logger("Migration002Proxmox")

    def upgrade(self, db: Database):
        collection = db['topology'].find()

        for topology_item in collection:
            vims_list = topology_item['vims']
            for vim_item in vims_list:
                # Old unused parameter
                if "osm_onboard" in vim_item.keys():
                    del vim_item['osm_onboard']
                if "schema_version" in vim_item.keys():
                    del vim_item['schema_version']

                openstack_parameters = {}
                if "vim_tenant_name" in vim_item.keys():
                    openstack_parameters["project_name"] = vim_item['vim_tenant_name']
                    del vim_item['vim_tenant_name']
                # Only if there were openstack parameters, we change them
                if len(openstack_parameters.keys()) > 0:
                    vim_item['vim_openstack_parameters'] = openstack_parameters


                # Initialize vim_proxmox_parameters
                proxmox_parameters = {}
                if "vim_proxmox_realm" in vim_item.keys():
                    proxmox_parameters['proxmox_realm'] = vim_item['vim_proxmox_realm']
                    del vim_item['vim_proxmox_realm']

                if "vim_proxmox_node" in vim_item.keys():
                    proxmox_parameters['proxmox_node'] = vim_item['vim_proxmox_node']
                    del vim_item['vim_proxmox_node']

                if "vim_proxmox_images_volume" in vim_item.keys():
                    proxmox_parameters['proxmox_images_volume'] = vim_item['vim_proxmox_images_volume']
                    del vim_item['vim_proxmox_images_volume']

                if "vim_proxmox_vm_volume" in vim_item.keys():
                    proxmox_parameters['proxmox_vm_volume'] = vim_item['vim_proxmox_vm_volume']
                    del vim_item['vim_proxmox_vm_volume']

                if "vim_proxmox_token_name" in vim_item.keys():
                    proxmox_parameters['proxmox_token_name'] = vim_item['vim_proxmox_token_name']
                    del vim_item['vim_proxmox_token_name']

                if "vim_proxmox_token_value" in vim_item.keys():
                    proxmox_parameters['proxmox_token_value'] = vim_item['vim_proxmox_token_value']
                    del vim_item['vim_proxmox_token_value']

                if "vim_proxmox_otp_code" in vim_item.keys():
                    proxmox_parameters['proxmox_otp_code'] = vim_item['vim_proxmox_otp_code']
                    del vim_item['vim_proxmox_otp_code']
                # Only if there was a proxmox parameter, we change them
                if len(proxmox_parameters.keys()) > 0:
                    vim_item['vim_proxmox_parameters'] = proxmox_parameters

            db['topology'].update_one({"_id": topology_item["_id"]}, {"$set": {"vims": vims_list}})



    def downgrade(self, db: Database):
        pass
