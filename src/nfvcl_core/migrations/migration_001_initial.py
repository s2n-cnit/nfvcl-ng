from pymongo.synchronous.database import Database

from nfvcl_core.migrations import Migration
from nfvcl_core.utils.log import create_logger


class Migration001Initial(Migration):
    def __init__(self):
        self.logger = create_logger("Migration001Initial")

    def upgrade(self, db: Database):
        self.logger.info("Test migration upgrade")

    def downgrade(self, db: Database):
        pass
