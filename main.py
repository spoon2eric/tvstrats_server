import logging.config
import os
import time
from dotenv import load_dotenv
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
        ui_collection = mongo_conn.ui_collection
        record = ui_collection.find_one({"ticker": ticker, "time_frame": time_frame})
        
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

def update_ui_collection(ticker, time_frame, stage=None, is_red_dot=None, is_green_dot=None, money_flow=None, start_time=None, big_green_dot_time=None, red_dot_time=None, green_dot_time=None):
    with MongoConnection() as mongo_conn:
        ui_collection = mongo_conn.ui_collection
        
        update_data = {
            "stage": stage, 
            "last_updated": time.time(),
            "start_time": start_time,
            "big_green_dot_time": big_green_dot_time,
            "red_dot_time": red_dot_time,
            "green_dot_time": green_dot_time,
            "is_red_dot": is_red_dot,
            "is_green_dot": is_green_dot,
            "money_flow": money_flow
        }
        
        # Remove keys with None values
        update_data = {k: v for k, v in update_data.items() if v is not None}
        
        ui_collection.update_one(
            {"ticker": ticker, "time_frame": time_frame},
            {"$set": update_data},
            upsert=True
        )
        
        logger = logging.getLogger('mainLogger')
        logger.info(f"Updated UI collection for {ticker}-{time_frame} to stage {stage}")



def job():
    logger = logging.getLogger('mainLogger')
    
    logger.info("Starting job function")

    dot_tickers = get_all_dot_tickers_from_file()
    if not dot_tickers:
        logger.warning("No dot tickers found")
        return

    logger.info(f"Found {len(dot_tickers)} dot tickers. Getting current green and red dots for all tickers and timeframes")
    dot_data_list = get_and_store_dot_data(dot_tickers)

    for dot_data in dot_data_list:
        update_ui_collection(
            dot_data["ticker"], 
            dot_data["time_frame"], 
            is_red_dot=dot_data["is_red_dot"], 
            is_green_dot=dot_data["is_green_dot"], 
            money_flow=dot_data["money_flow"]
        )

    tickers = get_all_tickers_from_file()
    for ticker_info in tickers:
        ticker = ticker_info["ticker_symbol"]
        time_frame = ticker_info["time_frame"]
        current_stage, start_time, big_green_dot_time, red_dot_time, green_dot_time = get_current_stage(ticker, time_frame)
        red_dot_value = None  # Initialize red_dot_value here

        if current_stage == 0:
            result = stage1.find_big_green_dot(ticker, time_frame)
            if result:
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
            result = stage2.find_red_dot(ticker, time_frame, start_time)
            if result and result["Stage"] != 0:
                red_dot_time = result["TV Time"]
                red_dot_value = result["Red Dot Value"]  # Get the red dot value from the result
                logger.info(f"Setting stage to 2 from main")
                update_ui_collection(ticker, time_frame, 2, start_time=start_time, big_green_dot_time=big_green_dot_time, red_dot_time=red_dot_time)
                current_stage = 2  # Update current_stage for immediate next stage check
            else:
                update_ui_collection(ticker, time_frame, 1)  # Keep stage at 1 if pattern is not broken
                continue  # Skip to next iteration as pattern is broken

        if current_stage == 2:
            if red_dot_value is not None:
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
                # Log an error or take appropriate action since red_dot_value is not available
                continue

        if current_stage == 3:
            result = reset_dots_stage.reset_dots(ticker, time_frame)
            if result:
                update_ui_collection(ticker, time_frame, **result)
                # No need to continue as the pattern has been reset
                continue



def main():
    setup_logging()
    logger = logging.getLogger('mainLogger')
    version = os.getenv("VERSION")
    if version is None:
        logger.warning('VERSION is not set in .env file')
    else:
        logger.info('__main__ tvstrats_server version: %s', version)

    setup_mongodb()
    logger.info("========================")
    # Set up the schedule
    schedule_interval = int(os.getenv("SCHEDULE_INTERVAL", 12))
    schedule.every(schedule_interval).minute.do(job)

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
