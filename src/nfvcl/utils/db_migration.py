import importlib
import os
from pymongo import MongoClient

from nfvcl.models.config_model import NFVCLConfigModel
from nfvcl.utils.util import get_nfvcl_config
from nfvcl.utils.database import get_nfvcl_database
from nfvcl.utils.log import create_logger

logger = create_logger("DB Migrations")
nfvcl_config: NFVCLConfigModel = get_nfvcl_config()
mongo_client: MongoClient = get_nfvcl_database().mongo_client
db = mongo_client.get_database(nfvcl_config.mongodb.db)

if 'migrations' not in db.list_collection_names():
    db.create_collection('migrations')

migrations_collection = db.get_collection('migrations')

def get_applied_migrations():
    return set(migration['name'] for migration in migrations_collection.find())

def apply_migration(migration_name, migration_module):
    print(f"Applying migration {migration_name}")
    migration_module.upgrade(db)
    migrations_collection.insert_one({'name': migration_name})

def rollback_migration(migration_name, migration_module):
    print(f"Rolling back migration {migration_name}")
    migration_module.downgrade(db)
    migrations_collection.delete_one({'name': migration_name})

def start_migrations():
    applied_migrations = get_applied_migrations()
    migration_files = sorted(
        f for f in os.listdir('src/nfvcl/utils/migrations') if f.startswith('migration_') and f.endswith('.py')
    )

    for migration_file in migration_files:
        migration_name = migration_file.split(".")[0]
        if migration_name not in applied_migrations:
            migration_module = importlib.import_module(f'nfvcl.utils.migrations.{migration_name}')
            apply_migration(migration_name, migration_module)

