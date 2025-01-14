import abc

from pymongo.synchronous.database import Database


class Migration(abc.ABC):
    @abc.abstractmethod
    def upgrade(self, db: Database):
        pass

    @abc.abstractmethod
    def downgrade(self, db: Database):
        pass
