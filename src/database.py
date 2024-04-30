import os
import dotenv
from sqlalchemy import create_engine
import sqlalchemy

def database_connection_url():
    dotenv.load_dotenv()

    return os.environ.get("POSTGRES_URI")

engine = create_engine(database_connection_url())

# create tables in metadata
metadata_obj = sqlalchemy.MetaData()

processed = sqlalchemy.Table("processed", metadata_obj, autoload_with=engine)
potion_types = sqlalchemy.Table("potion_types", metadata_obj, autoload_with=engine)
potions = sqlalchemy.Table("potions", metadata_obj, autoload_with=engine)
gold_ledger = sqlalchemy.Table("gold_ledger", metadata_obj, autoload_with=engine)
potion_ledger = sqlalchemy.Table("potion_ledger", metadata_obj, autoload_with=engine)
carts = sqlalchemy.Table("carts", metadata_obj, autoload_with=engine)
