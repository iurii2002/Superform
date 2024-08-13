import time
import random

from loguru import logger

from config import sleeping_time, log_file, keys_file, morpho_well_eth_vault_id, eth_address, minimum_balance_left
from modules.superform_sdk import MySuperform
from utils.helpful_scripts import load_accounts_from_keys, load_logger, catch_errors
from utils.constants import BreakTimer


@catch_errors(sleeping_time)
def claim_rewards(account, season):
    super_bot = MySuperform(account=account)
    return super_bot.claim_all_rewards(season)


@catch_errors(sleeping_time)
def get_portfolio(account):
    super_bot = MySuperform(account=account)
    normalized_balance = super_bot.get_normalize_amount(super_bot.native_balance, 18)
    logger.info(f'native balance: {normalized_balance}')
    logger.info(super_bot.get_portfolio())


@catch_errors(sleeping_time)
def deposit(account, vault_id, token_address=eth_address):
    super_bot = MySuperform(account=account)

    if token_address == eth_address:
        normalized_balance = super_bot.get_normalize_amount(super_bot.native_balance, 18)

        if normalized_balance < minimum_balance_left:
            logger.info(f'Native balance is lower then minimum needed - {normalized_balance} < {minimum_balance_left}')
            raise BreakTimer()

        # deposit 90 - 95 % of balance
        amount = (normalized_balance * random.randint(9000, 9500) / 10000)
    else:

        # deposit 100% of token balance
        amount = super_bot.get_normalize_amount(super_bot.get_token_balance(token_address=token_address),
                                                super_bot.get_decimals(token_address=token_address))
        # dust token balance
        if amount < 0.01:
            logger.info(f'Already deposited, token balance {amount}')
            return BreakTimer()

    return super_bot.deposit_single_vault(vault_id=vault_id, amount=amount, token_address=token_address)


@catch_errors(sleeping_time)
def withdraw(account, vault_id, token_address=eth_address):
    super_bot = MySuperform(account=account)
    return super_bot.withdraw_single_vault(vault_id=vault_id, withdraw_percent=100, token_address=token_address)


def deposit_to_morpho(account, token_address=eth_address):
    return deposit(account, morpho_well_eth_vault_id, token_address=token_address)


def withdraw_from_morpho(account):
    return withdraw(account, morpho_well_eth_vault_id)


def use_script():
    accounts = load_accounts_from_keys(keys_file)
    total_account = len(accounts)
    logger.info(f"Loaded for {total_account} accounts")

    random.shuffle(accounts)
    for account in accounts:
        # while True:
        # account = accounts[random.randint(0, len(accounts) - 1)]

        load_logger(log_file)
        logger.info(f'Started for wallet {account.address}')
        random_sleep = random.randint(*sleeping_time['default'])

        # todo uncomment necessary script the script
        claim_rewards(account=account, season=3)
        # withdraw_from_morpho(account=account)
        # deposit_to_morpho(account=account)
        # get_portfolio(account=account)

        logger.info(f"Sleeping for {random_sleep} seconds")
        time.sleep(random_sleep)


if __name__ == '__main__':
    use_script()
