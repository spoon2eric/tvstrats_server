import logging
from services.db_conn import MongoConnection

logger = logging.getLogger('mainLogger')

def get_and_store_dot_data(dot_tickers):
    logger.info("Entering get_and_store_dot_data function")
    dot_data_list = []
    for ticker, time_frame in dot_tickers:
        try:
            with MongoConnection() as mongo_conn:
                mc_collection = mongo_conn.collection

                # Find the most recent record with a non-"null" Blue Wave Crossing UP or Down
                record = mc_collection.find_one(
                    {
                        "Time Frame": time_frame, 
                        "ticker": ticker, 
                        "$or": [
                            {"Blue Wave Crossing UP": {"$ne": "null"}},
                            {"Blue Wave Crossing Down": {"$ne": "null"}}
                        ]
                    },
                    sort=[('TV Time', -1)]
                )

                if not record:
                    logger.info(f"No dot found for {ticker}-{time_frame}")
                    continue

                # Determine dot color
                is_red_dot = is_green_dot = "FALSE"
                if record['Blue Wave Crossing UP'] != "null":
                    is_green_dot = "TRUE"
                elif record['Blue Wave Crossing Down'] != "null":
                    is_red_dot = "TRUE"

                # Fetch the most recent "Mny Flow" for each ticker and time frame
                money_flow_record = mc_collection.find_one(
                    {"Time Frame": time_frame, "ticker": ticker}, 
                    sort=[('TV Time', -1)]
                )
                
                money_flow = money_flow_record['Mny Flow'] if money_flow_record and 'Mny Flow' in money_flow_record else None

                dot_data = {
                    "ticker": ticker,
                    "time_frame": time_frame,
                    "is_red_dot": is_red_dot,
                    "is_green_dot": is_green_dot,
                    "money_flow": money_flow
                }
                dot_data_list.append(dot_data)
                logger.info(f"Collected data for {ticker}-{time_frame}")

        except Exception as e:
            logger.error(f"Error collecting data for {ticker}-{time_frame}: {e}")
            
    return dot_data_list
