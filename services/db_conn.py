import logging
import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv(dotenv_path="./config/.env")

class MongoConnection:
    DB_NAME = "market_data"
    COLLECTION_NAME = "market_cipher_b"
    TRADES_COLLECTION_NAME = "trades"
    UI_COLLECTION_NAME = "user_interface"

    def __init__(self):
        self.client = None
        self.db = None
        self.collection = None
        self.trades_collection = None
        self.ui_collection = None

    def __enter__(self):
        MONGO_USERNAME = os.getenv("MONGO_USERNAME")
        MONGO_PASSWORD = os.getenv("MONGO_PASSWORD")
        MONGO_IP = os.getenv("MONGO_IP")
        MONGO_PORT = "27017"
        MONGO_URI = f"mongodb://{MONGO_USERNAME}:{MONGO_PASSWORD}@{MONGO_IP}:{MONGO_PORT}/?authMechanism=DEFAULT"

        self.client = MongoClient(MONGO_URI)
        self.db = self.client[self.DB_NAME]
        self.collection = self.db[self.COLLECTION_NAME]
        self.trades_collection = self.db[self.TRADES_COLLECTION_NAME]
        self.ui_collection = self.db[self.UI_COLLECTION_NAME]
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.client.close()

def setup_mongodb():
    logging.info("Setting up MongoDB...")
    try:
        with MongoConnection() as mongo_conn:
            db = mongo_conn.db
            for collection_name in [MongoConnection.COLLECTION_NAME, MongoConnection.TRADES_COLLECTION_NAME, MongoConnection.UI_COLLECTION_NAME]:
                if collection_name not in db.list_collection_names():
                    db.create_collection(collection_name)
                    logging.info(f"Collection {collection_name} created.")
                else:
                    logging.info(f"Collection {collection_name} already exists.")
            logging.info("MongoDB setup completed successfully.")
    except Exception as e:
        logging.error(f"Error setting up MongoDB: {e}")
