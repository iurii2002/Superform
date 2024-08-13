import time
import random
import requests

from loguru import logger
from web3 import Web3

from utils.helpful_scripts import (load_accounts_from_keys, load_accounts_from_keys_encrypted, get_native,
                                   get_network_by_chain_id, load_logger, send_error_message, max_gas)
from utils.constants import BreakTimer
from config import minimum_balance_left, keys_file
from modules.superform_sdk import MySuperform

# FILE SETTINGS

# file_keys = 'files/key_test'

# withdraw from harvest finance
# file_keys = 'files/keys1'  #  wallets 400 - 499


file_keys = 'files/keys2'  #  wallets ??? - ???
# file_keys = 'files/keys3'  #  wallets 200 - 299
file_log = 'logs/superform'

# GENERAL SETTINGS
script_name = 'superform'


def claim_rewards(account, season):
    super_bot = MySuperform(account=account)
    print(super_bot.get_protocol_rewards())
    # return super_bot.claim_all_rewards(season)


def deposit(account, vault_id, token_address='0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE'):
    super_bot = MySuperform(account=account)

    if token_address == '0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE':
        normalized_balance = super_bot.get_normalize_amount(super_bot.native_balance, 18)
        logger.info(f'native balance: {normalized_balance} '
                    f'in USD {int(normalized_balance * 3500)}')

        if normalized_balance < minimum_balance_left:
            raise BreakTimer()

        amount = (normalized_balance * random.randint(9000, 9500) / 10000)
    else:

        amount = super_bot.get_normalize_amount(super_bot.get_token_balance(token_address=token_address),
                                                super_bot.get_decimals(token_address=token_address))
        if amount < 0.01:
            logger.info(f'Already deposited, token balance {amount}')
            return BreakTimer()
    return super_bot.deposit_single_vault(vault_id=vault_id, amount=amount, token_address=token_address)


def withdraw(account, vault_id, token_address='0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE'):
    super_bot = MySuperform(account=account)
    return super_bot.withdraw_single_vault(vault_id=vault_id, withdraw_percent=100, token_address=token_address)


def deposit_to_morpho(account, token_address='0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE'):
    morpho_vault_id = 'pxOqM7dFwI2Abt-yTv4jC'
    deposit(account, morpho_vault_id, token_address=token_address)


def withdraw_from_morpho(account):
    morpho_vault_id = 'pxOqM7dFwI2Abt-yTv4jC'
    withdraw(account, morpho_vault_id)


def get_portfolio(account):
    super_bot = MySuperform(account=account)
    logger.info(f'native balance: {super_bot.native_balance / (10**18)} in USD {super_bot.native_balance * 3500 / (10**18)}')
    logger.info(super_bot.get_portfolio())


def use_script():
    accounts = load_accounts_from_keys_encrypted(file_keys)
    # accounts = load_accounts_from_keys(file_keys)

    total_account = len(accounts)
    logger.info(f"Loaded for {total_account} accounts")

    random.shuffle(accounts)
    for account in accounts:

    # while True:
        load_logger(file_log)
        # account = accounts[random.randint(0, len(accounts) - 1)]
        logger.info(f'Started for wallet {account.address}')
        # random_sleep = random.randint(150, 250)
        random_sleep = random.randint(15, 35)
        weth_address = '0x4200000000000000000000000000000000000006'
        try:
            claim_rewards(account=account, season=3)
            # withdraw_from_harvest(account=account)
            # time.sleep(5)
            # deposit_to_morpho(account=account)
        except BreakTimer:
            random_sleep = random.randint(1, 3)
        except requests.exceptions.ConnectionError as connect:
            logger.error(f'ConnectionError {account.address} : {connect}')
            random_sleep = random.randint(50, 100)
        except ValueError as value:
            logger.error(f'ValueError {account.address} : {value}')
            random_sleep = random.randint(5, 10)
        except Exception as err:
            logger.error(f'Something went wrong with account {account.address} : {err}')
            random_sleep = random.randint(5, 10)
            send_error_message(message=f'other error {err}', script=script_name)

        logger.info(f"Sleeping for {random_sleep} seconds")
        time.sleep(random_sleep)


if __name__ == '__main__':
    use_script()
