import logging
from datetime import datetime, timezone
from services.db_conn import MongoConnection

def reset_dots(ticker, time_frame):
    logger = logging.getLogger('mainLogger')

    with MongoConnection() as mongo_conn:
        ui_collection = mongo_conn.ui_collection
        mc_collection = mongo_conn.collection

        # Find the UI record for the given ticker and time frame with stage 3
        ui_record = ui_collection.find_one({"ticker": ticker, "time_frame": time_frame, "stage": 3})
        
        if ui_record:
            green_dot_time_str = ui_record["green_dot_time"]
            green_dot_time = datetime.strptime(green_dot_time_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            green_dot_time_str_mongo = green_dot_time.strftime("%Y-%m-%d %H:%M:%S")

            # Find any red dots in the MarketCipher B collection after the green dot time
            new_red_dot = mc_collection.find_one(
                {
                    "ticker": ticker,
                    "Time Frame": time_frame,
                    "TV Time": {"$gt": green_dot_time_str_mongo},
                    "Blue Wave Crossing Down": {"$ne": "null"}
                },
                sort=[("TV Time", 1)]  # Sorting in ascending order
            )

            if new_red_dot:
                # Prepare data to clear out all fields except for the Big Green Dot time and reset the stage to 0
                update_data = {
                    "stage": 0,
                    "start_time": None,
                    "red_dot_time": None,
                    "green_dot_time": None,
                    "big_green_dot_time": None
                }
                logger.info(f"(Reset) Reset stage to 0 and cleared fields for {ticker}-{time_frame} as a new red dot is found after the green dot at {new_red_dot['TV Time']}")
                return update_data
            else:
                logger.info(f"(Reset) No new red dot found after the green dot for {ticker}-{time_frame} at {green_dot_time}. No action taken.")
        else:
            logger.info(f"No stage 3 record found for {ticker}-{time_frame}. No action taken.")
    return None
