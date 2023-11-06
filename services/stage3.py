import logging
from services.db_conn import MongoConnection
from datetime import datetime, timedelta

def find_green_dot(ticker, time_frame, red_dot_time_str, red_dot_value):
    logger = logging.getLogger('mainLogger')
    logger.debug("Entering find_green_dot()")

    # Convert red dot time to datetime object and add 1 second
    red_dot_time = datetime.strptime(red_dot_time_str, "%Y-%m-%dT%H:%M:%SZ")
    search_start_time = red_dot_time + timedelta(seconds=1)
    logger.info(f"S3: Searching for green dots after {search_start_time} for {ticker}-{time_frame}")

    with MongoConnection() as mongo_conn:
        collection = mongo_conn.collection

        # Find all records after the search_start_time for the given ticker and time frame, sorted by TV Time in ascending order
        records = collection.find(
            {"ticker": ticker, "Time Frame": time_frame, "TV Time": {"$gt": search_start_time.isoformat() + "Z"}},
            sort=[("TV Time", 1)]
        )

        for record in records:
            green_dot_time_str = record["TV Time"]
            green_dot_time = datetime.strptime(green_dot_time_str, "%Y-%m-%dT%H:%M:%SZ")

            # Check for higher red dot
            red_dot_value_str = record.get('Blue Wave Crossing Down')
            red_dot_time_str = record.get('TV Time')
            if red_dot_value_str is not None and red_dot_value_str != 'null':
                new_red_dot_value = float(red_dot_value_str)
                if new_red_dot_value > red_dot_value:
                    logger.info(f"S3: Breaking sequence: Found higher Red Dot at {red_dot_time_str}")
                    return {"Stage": 0, "TV Time": None, "red_dot_time": None, "big_green_dot_time": None}

            # Check for green dot
            green_dot_value_str = record.get('Blue Wave Crossing UP')
            logger.info(f"S3: Checking green dot at {green_dot_time} with value {green_dot_value_str} and time {green_dot_time_str}")

            if green_dot_value_str is not None and green_dot_value_str != 'null':
                green_dot_value = float(green_dot_value_str)
                if green_dot_value <= -9:  # Value for Stage 3 green dot
                    logger.info(f"S3: Green Dot found for {ticker}-{time_frame} at {green_dot_time}: {record}")
                    return {"Stage": 3, "TV Time": green_dot_time_str}

        # If no green dot is found after the red dot, log the information and return None
        logger.info(f"S3: No Green Dot found for {ticker}-{time_frame} after Red Dot at {red_dot_time_str}")
        return None
