import logging
from pymongo import DESCENDING
from services.db_conn import MongoConnection

def find_big_green_dot(ticker, time_frame):
    logger = logging.getLogger('mainLogger')
    logger.debug("Entering find_big_green_dot()")
    with MongoConnection() as mongo_conn:
        collection = mongo_conn.collection
        query = {
            "ticker": ticker,
            "Time Frame": time_frame,
            "Buy": "1"
        }
        logger.debug(f"Query for big green dot: {query}")
        
        record = collection.find_one(query, sort=[("TV Time", DESCENDING)])
        
        if record:
            green_dot_time = record["TV Time"]  # Capture the TV Time of the red dot
            logger.info(f"Stage 1, BIG GREEN DOT TIME for {ticker}-{time_frame}: {green_dot_time}")
            return {"Stage": 1, "TV Time": green_dot_time}
        else:
            logger.warning(f"No Big Green Dot found for {ticker}-{time_frame} with query {query}")
            return {"Stage": 0, "TV Time": None}
