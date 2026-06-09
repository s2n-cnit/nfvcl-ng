from pymongo.synchronous.database import Database

from nfvcl_common.utils.log import create_logger
from nfvcl_core.migrations.base_class_migration import Migration


class Migration006TopologyCallback(Migration):
    def __init__(self):
        self.logger = create_logger("Migration006TopologyCallback")

    def upgrade(self, db: Database) -> None:
        result = db["topology"].update_many(
            {"callback": {"$exists": True}},
            {"$unset": {"callback": ""}},
        )
        self.logger.info(f"Removed callback field from {result.modified_count} topology documents")

    def downgrade(self, db: Database) -> None:
        pass
