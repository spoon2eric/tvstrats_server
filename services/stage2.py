import logging
from services.db_conn import MongoConnection

def find_red_dot(ticker, time_frame, start_time):
    logger = logging.getLogger('mainLogger')
    logger.debug("Entering find_red_dot()")
    with MongoConnection() as mongo_conn:
        collection = mongo_conn.collection

        stage = 1
        last_red_dot_value = float('-inf')
        red_dot_time = None  # Initialize red_dot_time

        records = collection.find({
            "ticker": ticker,
            "Time Frame": time_frame,
            "TV Time": {"$gt": start_time}
        }).sort("TV Time", 1)

        for record in records:
            if stage == 1:
                #logger.info(f"Record in stage2: {record}")
                red_dot_value_str = record.get('Blue Wave Crossing Down')
                if red_dot_value_str and red_dot_value_str != 'null':
                    red_dot_value = float(red_dot_value_str)
                    if red_dot_value >= 9:  # Change this value to find First Red Dot
                        stage = 2
                        red_dot_time = record["TV Time"]  # Capture the TV Time of the red dot
                        logger.info(f"Stage 2, RED DOT TIME for {ticker}-{time_frame}: {red_dot_time}")
                        logger.info(f"Stage 2 set due to Red Dot: {record}")
                    else:
                        logger.debug(f"Red Dot (Stage 1): {record}")
                    if red_dot_value > last_red_dot_value and red_dot_value < 0:
                        last_red_dot_value = red_dot_value

        if stage == 2:
            logger.info(f"Red Dot (Stage 2) found for {ticker}-{time_frame} at {red_dot_time}")
            return {"Stage": 2, "TV Time": red_dot_time, "Red Dot Time": red_dot_time, "Red Dot Value": red_dot_value}
        else:
            logger.info(f"No Red Dot (Stage 2) found for {ticker}-{time_frame}")
            stage = 0
            logger.info(f"S2 Set stage to 0 for {ticker}-{time_frame} with Red Dot Time of {red_dot_time}")
            return {"Stage": 0, "TV Time": None, "Red Dot Time": None}
