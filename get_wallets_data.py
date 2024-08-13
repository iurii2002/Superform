import time
import random

from loguru import logger

from config import sleeping_time, log_file, wallets_file
from modules.superform_api import SuperFormApi
from utils.helpful_scripts import load_wallets, load_logger, catch_errors


@catch_errors(sleeping_time)
def get_points_wallets(address):
    api_bot = SuperFormApi()
    logger.info(api_bot.get_safari_points(address=address, season=4))


def use_script():
    addresses = load_wallets(wallets_file)
    total_account = len(addresses)
    logger.info(f"Loaded for {total_account} accounts")

    for address in addresses:
        load_logger(log_file)
        random_sleep = random.randint(1, 3)
        get_points_wallets(address=address)
        time.sleep(random_sleep)


if __name__ == '__main__':
    use_script()
