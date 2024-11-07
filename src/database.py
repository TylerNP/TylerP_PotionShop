import os 
import dotenv
import sqlalchemy
from sqlalchemy import create_engine

def database_connection_url():
    dotenv.load_dotenv()

    return os.environ.get("POSTGRES_URI")

engine = create_engine(database_connection_url(), pool_pre_ping=True)
metadata_obj = sqlalchemy.MetaData()
customers = sqlalchemy.Table("customers", metadata_obj, autoload_with=engine)
transactions = sqlalchemy.Table("transactions", metadata_obj, autoload_with=engine)
customer_purchases = sqlalchemy.Table("customer_purchases", metadata_obj, autoload_with=engine)
potion_ledgers = sqlalchemy.Table("potion_ledgers", metadata_obj, autoload_with=engine)

