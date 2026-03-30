from pymongo.synchronous.database import Database

from nfvcl_core.migrations.base_class_migration import Migration
from nfvcl_common.utils.log import create_logger


class Migration005PduLock(Migration):
    def __init__(self):
        self.logger = create_logger("Migration005PduLock")

    def upgrade(self, db: Database):
        """
        Migrate PDU locked_by field to locked_list_by field.
        Transforms the single string locked_by field into a list of PduLock objects.
        """
        topology_collection = db['topology']

        # Find all topology documents
        for topology_doc in topology_collection.find():
            if 'pdus' not in topology_doc:
                continue

            pdus_updated = False
            updated_pdus = []

            for pdu in topology_doc['pdus']:
                # Check if the old field exists and is not None
                if 'locked_by' in pdu and pdu['locked_by'] is not None:
                    # Convert locked_by string to locked_list_by list
                    # Determine lock type based on instance_type
                    instance_type = pdu.get('instance_type', '')
                    lock_type = 'GENERIC' if instance_type in ['AthonetCore', 'AthonetUpf'] else 'CORE'

                    pdu['locked_list_by'] = [{
                        'type': lock_type,
                        'blueprint_id': pdu['locked_by']
                    }]
                    # Remove the old field
                    del pdu['locked_by']
                    pdus_updated = True
                elif 'locked_by' in pdu:
                    # locked_by exists but is None, convert to empty list
                    pdu['locked_list_by'] = []
                    del pdu['locked_by']
                    pdus_updated = True
                elif 'locked_list_by' not in pdu:
                    # Ensure locked_list_by exists even if locked_by didn't exist
                    pdu['locked_list_by'] = []
                    pdus_updated = True

                updated_pdus.append(pdu)

            # Update the topology document if any PDU was modified
            if pdus_updated:
                topology_collection.update_one(
                    {"_id": topology_doc["_id"]},
                    {"$set": {"pdus": updated_pdus}}
                )
                self.logger.info(f"Updated topology document {topology_doc.get('_id')} with new PDU lock structure")

    def downgrade(self, db: Database):
        pass
        # """
        # Revert PDU locked_list_by field back to locked_by field.
        # Takes the first lock from the list (if any) and sets it as locked_by string.
        # """
        # topology_collection = db['topology']
        #
        # # Find all topology documents
        # for topology_doc in topology_collection.find():
        #     if 'pdus' not in topology_doc:
        #         continue
        #
        #     pdus_updated = False
        #     updated_pdus = []
        #
        #     for pdu in topology_doc['pdus']:
        #         # Check if the new field exists
        #         if 'locked_list_by' in pdu:
        #             # Convert locked_list_by list back to locked_by string
        #             if pdu['locked_list_by'] and len(pdu['locked_list_by']) > 0:
        #                 # Take the first lock in the list
        #                 pdu['locked_by'] = pdu['locked_list_by'][0]['blueprint_id']
        #             else:
        #                 pdu['locked_by'] = None
        #
        #             # Remove the new field
        #             del pdu['locked_list_by']
        #             pdus_updated = True
        #
        #         updated_pdus.append(pdu)
        #
        #     # Update the topology document if any PDU was modified
        #     if pdus_updated:
        #         topology_collection.update_one(
        #             {"_id": topology_doc["_id"]},
        #             {"$set": {"pdus": updated_pdus}}
        #         )
        #         self.logger.info(f"Reverted topology document {topology_doc.get('_id')} to old PDU lock structure")
