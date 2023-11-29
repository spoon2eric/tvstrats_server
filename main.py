import logging.config
import os
import time
from dotenv import load_dotenv
import requests
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from services.db_conn import setup_mongodb, MongoConnection
from services import stage1, stage2, stage3, reset_dots_stage
from services.get_dots import get_and_store_dot_data
import schedule

dotenv_path = "./config/.env"
load_dotenv(dotenv_path=dotenv_path)

class FileChangeHandler(FileSystemEventHandler):
    def on_modified(self, event):
        logger = logging.getLogger('mainLogger')
        if 'tickers.txt' in event.src_path:
            logger.info("tickers.txt has been modified, updating tickers...")
            get_all_tickers_from_file()
        elif 'dot_tickers.txt' in event.src_path:
            logger.info("dot_tickers.txt has been modified, updating dot tickers...")
            get_all_dot_tickers_from_file()

def get_all_tickers_from_file():
    tickers = []
    with open('./config/tickers.txt', 'r') as f:
        for line in f.readlines():
            ticker, time_frame = line.strip().split(', ')
            tickers.append({"ticker_symbol": ticker, "time_frame": time_frame})
    return tickers

def get_all_dot_tickers_from_file():
    dot_tickers = []
    with open('./config/dot_tickers.txt', 'r') as f:
        for line in f.readlines():
            ticker, time_frame = line.strip().split(', ')
            dot_tickers.append((ticker, time_frame))
    return dot_tickers

def setup_logging():
    default_path = './config/logging_config.ini'
    default_level = logging.INFO
    env_key = 'LOG_CFG'
    path = default_path
    value = os.getenv(env_key, None)
    if value:
        path = value
    absolute_path = os.path.abspath(path)
    if os.path.exists(absolute_path):
        logging.config.fileConfig(absolute_path)
    else:
        logging.basicConfig(level=default_level)
    logger = logging.getLogger('mainLogger')
    if not os.path.exists(absolute_path):
        logger.warning(f"Logging config not found at {absolute_path}")

def get_current_stage(ticker, time_frame):
    with MongoConnection() as mongo_conn:
        logger = logging.getLogger('mainLogger')
        logger.info(f"Inside get_current_stage()")
        ui_collection = mongo_conn.ui_collection
        record = ui_collection.find_one({"ticker": ticker, "time_frame": time_frame})
        
        logger.info(f"Record: {record}")  # This will log the fetched record

        if record:
            return (
                record.get('stage', 0), 
                record.get('start_time'), 
                record.get('big_green_dot_time'), 
                record.get('red_dot_time'),
                record.get('green_dot_time')
            )
        else:
            return 0, None, None, None, None

def update_ui_collection(ticker, time_frame, stage=None, is_red_dot=None, is_green_dot=None, money_flow=None, start_time=None, big_green_dot_time=None, red_dot_time=None, green_dot_time=None, red_dot_value=None, price=None):
    logger = logging.getLogger('mainLogger')

    with MongoConnection() as mongo_conn:
        ui_collection = mongo_conn.ui_collection
        
        update_data = {
            "stage": stage, 
            "last_updated": time.time(),
            "price": price,
            "start_time": start_time,
            "big_green_dot_time": big_green_dot_time,
            "red_dot_time": red_dot_time,
            "green_dot_time": green_dot_time,
            "is_red_dot": is_red_dot,
            "is_green_dot": is_green_dot,
            "money_flow": money_flow,
            "red_dot_value": red_dot_value
        }
    
        # Remove keys with None values
        update_data = {k: v for k, v in update_data.items() if v is not None}
        logger.info(f"Update_data: {update_data}")
        ui_collection.update_one(
            {"ticker": ticker, "time_frame": time_frame},
            {"$set": update_data},
            upsert=True
        )
        if price is not None:
            logger.info(f"Updated {ticker} price: {price}")
        
        logger.info(f"Updated UI collection for {ticker}-{time_frame} to stage {stage}")


def update_ticker_prices():
    logger = logging.getLogger('mainLogger')
    logger.info("Updating ticker prices in ui_collection")

    # Retrieve the list of tickers from MongoDB or a file
    tickers = get_all_tickers_from_file()
    
    processed_tickers = set()  # Set to keep track of processed tickers

    for ticker_info in tickers:
        ticker = ticker_info["ticker_symbol"]
        if ticker not in processed_tickers:  # Check if the ticker has already been processed
            try:
                # Fetch and update the price data in ui_collection
                fetch_ticker_price(ticker)
                processed_tickers.add(ticker)  # Add the ticker to the set of processed tickers
            except Exception as e:
                logger.error(f"Error updating price for {ticker}: {e}")


def fetch_ticker_price(ticker_name):
    logger = logging.getLogger('mainLogger')
    time_frame = '15'  # Define the 15-minute time frame

    logger.info(f"Fetching price for: {ticker_name} with a {time_frame} minute time frame")

    try:
        with MongoConnection() as mongo_conn:
            # Query the market_cipher_b collection for the specific ticker and time frame
            query = {"ticker_symbol": ticker_name, "time_frame": time_frame}
            document = mongo_conn.collection.find_one(query)
            
            if document and 'close' in document:
                price = document['close']
                logger.info(f"Fetched price for {ticker_name}: {price}")

                # Update the ui_collection with the fetched price
                ui_update = {"$set": {"price": price}}
                mongo_conn.ui_collection.update_one({"ticker_symbol": ticker_name}, ui_update, upsert=True)

                return price
            else:
                logger.warning(f"Price data not available for the requested ticker {ticker_name}")
                return None
    except Exception as e:
        logger.error(f"Failed to fetch price from MongoDB: {e}")
        return None
    

def get_unique_ticker_prices(tickers):
    # This will strip 'USDT' only for the purpose of making the API call
    # The original ticker with 'USDT' will be stored in a dictionary with the stripped version as its key
    stripped_tickers = {ticker_info["ticker_symbol"].replace('USDT', ''): ticker_info["ticker_symbol"] for ticker_info in tickers}
    ticker_prices = {}

    for stripped_ticker, original_ticker in stripped_tickers.items():
        # Fetch the price using the stripped ticker
        price = fetch_ticker_price(stripped_ticker)
        if price is not None:
            # Store the price using the original ticker symbol
            ticker_prices[original_ticker] = price

    return ticker_prices

def update_ui_collection_with_prices(tickers, ticker_prices):
    logger = logging.getLogger('mainLogger')
    for ticker_info in tickers:
        original_ticker = ticker_info["ticker_symbol"]
        time_frame = ticker_info["time_frame"]

        # Use the fetched price, ensuring we use the original ticker symbol including 'USDT'
        price = ticker_prices.get(original_ticker)
        if price is not None:
            # Update the collection using the original ticker symbol
            update_ui_collection(original_ticker, time_frame, price=price)
            logger.info(f"Updated price for {original_ticker} at time frame {time_frame}.")
        else:
            logger.warning(f"No price fetched for ticker: {original_ticker}. Skipping update.")

def job():
    logger = logging.getLogger('mainLogger')
    
    logger.warning("Starting job function")

    dot_tickers = get_all_dot_tickers_from_file()
    if not dot_tickers:
        logger.warning("No dot tickers found")

    logger.info(f"Found {len(dot_tickers)} dot tickers. Getting current green and red dots for all tickers and timeframes")
    #Get Data for Dots.html
    dot_data_list = get_and_store_dot_data(dot_tickers)
    logger.info(f"dot_data_list: {dot_data_list}")

    for dot_data in dot_data_list:
        logger.info(f"{dot_data}")
        update_ui_collection(
            dot_data["ticker"], 
            dot_data["time_frame"], 
            is_red_dot=dot_data["is_red_dot"], 
            is_green_dot=dot_data["is_green_dot"], 
            money_flow=dot_data["money_flow"]
        )

    # Fetch tickers
    tickers = get_all_tickers_from_file()

    # Step 1: Fetch prices for unique tickers
    unique_tickers = set(ticker_info["ticker_symbol"] for ticker_info in tickers)
    ticker_prices = {}

    for ticker in unique_tickers:
        # Fetch the price for each unique ticker
        price = fetch_ticker_price(ticker)
        if price is not None:
            ticker_prices[ticker] = price
        else:
            logger.warning(f"Failed to fetch price for ticker: {ticker}")

    # Step 2: Update UI Collection with fetched prices
    for ticker_info in tickers:
        ticker = ticker_info["ticker_symbol"]
        time_frame = ticker_info["time_frame"]  # Make sure time_frame is retrieved from ticker_info

        # Use the fetched price for this ticker
        price = ticker_prices.get(ticker)
        if price is not None:
            update_ui_collection(ticker, time_frame, price=price)
            logger.info(f"Updated price for {ticker} at time frame {time_frame}.")
        else:
            logger.warning(f"No price fetched for ticker: {ticker}. Skipping update.")



    logger.info(f"Start loop for tickers")
    for ticker_info in tickers:
        logger.info(f"Inside loop ticker_info")
        ticker = ticker_info["ticker_symbol"]
        time_frame = ticker_info["time_frame"]
        logger.info(f"get_all_tickers_from_file - {ticker}-{time_frame}")
        
        current_stage, start_time, big_green_dot_time, red_dot_time, green_dot_time = get_current_stage(ticker, time_frame)
        
        logger.info(f"Returned from get_current_state(): {current_stage}-{start_time}-{big_green_dot_time}-{red_dot_time}-{green_dot_time}")
        red_dot_value = None  # Initialize red_dot_value here

        if current_stage == 0:
            logger.info(f"main current_stage = {current_stage}")
            result = stage1.find_big_green_dot(ticker, time_frame)
            logger.info(f"result from stage 0: {result}")
            if result and result.get("TV Time"):
                big_green_dot_time = result["TV Time"]
                logger.info(f"Setting stage to 1 from main, big green dot found {result}")
                update_ui_collection(ticker, time_frame, 1, big_green_dot_time=big_green_dot_time)
                current_stage = 1  # Update current_stage for immediate next stage check
                start_time = big_green_dot_time  # Update start_time for next stages
            else:
                logger.info(f"Setting stage to 0 from main, pattern is broken")
                update_ui_collection(ticker, time_frame, 0)  # Reset stage to 0 if pattern is broken
                continue  # Skip to next iteration as pattern is broken

        if current_stage == 1:
            logger.info(f"main current_stage = {current_stage}")
            result = stage2.find_red_dot(ticker, time_frame, start_time)
            logger.info(f"result from stage 1: {result}")
            if result and result["Stage"] != 0:
                red_dot_time = result["TV Time"]
                red_dot_value = result["Red Dot Value"]  # Get the red dot value from the result
                logger.info(f"Setting stage to 2 from main")
                update_ui_collection(ticker, time_frame, 2, start_time=start_time, big_green_dot_time=big_green_dot_time, red_dot_time=red_dot_time, red_dot_value=red_dot_value)
                current_stage = 2  # Update current_stage for immediate next stage check
            else:
                update_ui_collection(ticker, time_frame, 1)  # Keep stage at 1 if pattern is not broken
                continue  # Skip to next iteration as pattern is broken

        if current_stage == 2:
            result = stage2.find_red_dot(ticker, time_frame, start_time)
            logger.info(f"result from stage 2: {result}")
            red_dot_value = result["Red Dot Value"]
            logger.info(f"Inside current_stage == 2, red_dot_value is: {red_dot_value}")
            logger.info(f"main current_stage = {current_stage}")
            logger.info(f"Current stage: {current_stage}, Ticker: {ticker}, Time Frame: {time_frame}")
            logger.info(f"Red Dot Time: {red_dot_time}, Red Dot Value: {red_dot_value}")

            if red_dot_value is not None:
            #if red_dot_value is None:
                result = stage3.find_green_dot(ticker, time_frame, red_dot_time, red_dot_value)  # Pass the red dot value here
                if result:
                    if result["Stage"] == 0:
                        update_ui_collection(ticker, time_frame, 0)  # Reset stage to 0 if higher red dot is found
                        continue  # Skip to next iteration as pattern is broken
                    else:
                        green_dot_time = result["TV Time"]
                        update_ui_collection(ticker, time_frame, 3, start_time=start_time, big_green_dot_time=big_green_dot_time, red_dot_time=red_dot_time, green_dot_time=green_dot_time)
                        current_stage = 3  # Update current_stage for immediate next stage check
                else:
                    update_ui_collection(ticker, time_frame, 2)  # Keep stage at 2 if pattern is not broken
                    continue  # Skip to next iteration as pattern is broken
            else:
                logger.info(f"inside last else block of stage 2")
                # Log an error or take appropriate action since red_dot_value is not available
                continue

        if current_stage == 3:
            logger.info(f"main current_stage = {current_stage}")
            result = reset_dots_stage.reset_dots(ticker, time_frame)
            logger.info(f"result from stage 3: {result}")
            if result:
                update_ui_collection(ticker, time_frame, **result)
                # No need to continue as the pattern has been reset
                continue
    logger.warning("End of job function")

def main():
    setup_logging()
    logger = logging.getLogger('mainLogger')
    version = os.getenv("VERSION")
    if version is None:
        logger.warning('VERSION is not set in .env file')
    else:
        logger.warning('__main__ tvstrats_server version: %s', version)

    setup_mongodb()
    logger.warning("========================")
    # Set up the schedule
    schedule_interval = int(os.getenv("SCHEDULE_INTERVAL", 12))
    #schedule.every(schedule_interval).seconds.do(job)
    schedule.every(schedule_interval).minutes.do(job)
    # Set up the file change observer
    event_handler = FileChangeHandler()
    observer = Observer()
    observer.schedule(event_handler, path='./config', recursive=False)
    observer.start()

    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == '__main__':
    main()