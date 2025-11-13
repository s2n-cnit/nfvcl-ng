import importlib
import inspect
import os
import sys
from pathlib import Path
from typing import Optional

from pymongo import MongoClient
from pymongo.synchronous.collection import Collection
from pymongo.synchronous.database import Database

from nfvcl_core.migrations.base_class_migration import Migration
from nfvcl_core.managers.generic_manager import GenericManager


class PersistenceManager(GenericManager):
    def __init__(self, host: str, port: int, db: str, username: str = None, password: str = None, migration_base_class: Optional[type] = Migration):
        super().__init__()

        if username is not None and password is not None:
            uri = f"mongodb://{username}:{password}@{host}:{port}/"
        else:
            uri = f"mongodb://{host}:{port}/"
        self.mongo_client: MongoClient = MongoClient(uri)
        self.mongo_database: Database = self.mongo_client[db]
        if migration_base_class:
            self.migration_base_class = migration_base_class
            self.run_migrations()

    def get_database(self) -> Database:
        return self.mongo_database

    def get_collection(self, collection_name: str) -> Collection:
        return self.mongo_database[collection_name]

    def run_migrations(self):
        """
        Run migrations for the database
        """
        self.logger.debug("Checking for migrations")
        if 'migrations' not in self.mongo_database.list_collection_names():
            self.mongo_database.create_collection('migrations')
        migrations_collection = self.mongo_database.get_collection('migrations')
        applied_migrations = set(migration['name'] for migration in migrations_collection.find())

        migration_files = sorted(
            f for f in os.listdir(os.path.dirname(Path(sys.modules[self.migration_base_class.__module__].__file__))) if f.startswith('migration_') and f.endswith('.py')
        )

        for migration_file in migration_files:
            migration_name = migration_file.split(".")[0]
            if migration_name not in applied_migrations:
                self.logger.info(f"Applying migration {migration_name}")
                migration_module = importlib.import_module(f'{sys.modules[Migration.__module__].__package__}.{migration_name}')
                migration_object: Optional[Migration] = None
                for name, obj in inspect.getmembers(migration_module):
                    if inspect.isclass(obj) and issubclass(obj, Migration) and obj is not Migration:
                        migration_object = obj()
                        break
                if migration_object:
                    migration_object.upgrade(self.mongo_database)
                    del migration_object
                    migrations_collection.insert_one({'name': migration_name})
                else:
                    self.logger.error(f"Migration {migration_name} does not have a Migration class")
                del migration_module
                self.logger.info(f"Applied migration {migration_name}")

        self.logger.debug("Migrations done")
