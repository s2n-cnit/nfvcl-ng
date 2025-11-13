from pymongo.synchronous.database import Database

from nfvcl_core.migrations.base_class_migration import Migration
from nfvcl_common.utils.log import create_logger


class Migration004Providers(Migration):
    def __init__(self):
        self.logger = create_logger("Migration004Providers")

    def upgrade(self, db: Database):
        blueprints_collection = db['blueprints'].find()

        for blueprint_item in blueprints_collection:
            # Create a new provider document
            provider_doc = {
                "blueprint_id": blueprint_item["id"]
            }

            # Move virt_providers to virtualization
            if "virt_providers" in blueprint_item:
                provider_doc["virtualization"] = blueprint_item["virt_providers"]

            # Move k8s_providers to k8s
            if "k8s_providers" in blueprint_item:
                provider_doc["k8s"] = blueprint_item["k8s_providers"]

            # Move pdu_provider to pdu
            if "pdu_provider" in blueprint_item:
                provider_doc["pdu"] = blueprint_item["pdu_provider"]

            # Move blueprint_provider to blueprint
            if "blueprint_provider" in blueprint_item:
                provider_doc["blueprint"] = blueprint_item["blueprint_provider"]

            # Insert the new provider document into the providers collection
            db['providers'].insert_one(provider_doc)

            # Remove the fields from the blueprint document
            unset_fields = {}
            if "virt_providers" in blueprint_item:
                unset_fields["virt_providers"] = ""
            if "k8s_providers" in blueprint_item:
                unset_fields["k8s_providers"] = ""
            if "pdu_provider" in blueprint_item:
                unset_fields["pdu_provider"] = ""
            if "blueprint_provider" in blueprint_item:
                unset_fields["blueprint_provider"] = ""

            if unset_fields:
                db['blueprints'].update_one(
                    {"_id": blueprint_item["_id"]},
                    {"$unset": unset_fields}
                )

    def downgrade(self, db: Database):
        pass
        # providers_collection = db['providers'].find()
        #
        # for provider_item in providers_collection:
        #     blueprint_id = provider_item["blueprint_id"]
        #
        #     # Move fields back to blueprint
        #     set_fields = {}
        #     if "virtualization" in provider_item:
        #         set_fields["virt_providers"] = provider_item["virtualization"]
        #     if "k8s" in provider_item:
        #         set_fields["k8s_providers"] = provider_item["k8s"]
        #     if "pdu" in provider_item:
        #         set_fields["pdu_provider"] = provider_item["pdu"]
        #     if "blueprint" in provider_item:
        #         set_fields["blueprint_provider"] = provider_item["blueprint"]
        #
        #     if set_fields:
        #         db['blueprints'].update_one(
        #             {"_id": blueprint_id},
        #             {"$set": set_fields}
        #         )
        #
        #     # Delete the provider document
        #     db['providers'].delete_one({"_id": provider_item["_id"]})

