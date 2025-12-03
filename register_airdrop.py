import time
import random
import asyncio
import json
import os
from web3 import Web3
from loguru import logger
from eth_account.messages import encode_defunct

from capmonstercloudclient import CapMonsterClient, ClientOptions
from capmonstercloudclient.requests import RecaptchaV2Request

from requestor import SyncRequestor
from config import keys_file, capmonster_key
from utils.constants import BreakTimer
from utils.helpful_scripts import load_accounts_from_keys


class WalletStorage:
    def __init__(self, filename='files/wallets_registered.json'):
        self.filename = filename
        self.data = self._load()

    def _load(self):
        """Load existing data or create empty dict"""
        if os.path.exists(self.filename):
            with open(self.filename, 'r') as f:
                return json.load(f)
        return {}

    def _save(self):
        """Save data to file"""
        with open(self.filename, 'w') as f:
            json.dump(self.data, f, indent=2)

    def add(self, address, wallet_data):
        """Add wallet if it doesn't exist"""
        if address not in self.data:
            self.data[address] = wallet_data
            self._save()
            return True
        else:
            return False

    def get(self, address):
        """Get wallet data"""
        return self.data.get(address)

    def exists(self, address):
        """Check if address exists"""
        return address in self.data

    def get_all(self):
        """Get all wallets"""
        return self.data


proxy_file = 'files/proxies'
web3 = Web3()

def get_random_proxy(file_path):
    """Get a random proxy from txt file"""
    with open(file_path, 'r') as f:
        proxies = f.read().strip().split('\n')

    # Remove empty lines
    proxies = [proxy.strip() for proxy in proxies if proxy.strip()]

    # Get random proxy
    random_proxy = random.choice(proxies)
    return  {
                'http': f'http://{random_proxy}',
                'https': f'http://{random_proxy}',
            }

async def solve_captcha():
    client_options = ClientOptions(api_key=capmonster_key)  # Replace with your CapMonster Cloud API key
    cap_monster_client = CapMonsterClient(options=client_options)

    recaptcha2request = RecaptchaV2Request(
        websiteUrl="https://claim.superformfoundation.org/flow",
        websiteKey="6LcpM_MrAAAAAAT78yjGfIFE8XI3w54tCwCPeKXx",
    )

    async def solve_captcha():
        return await cap_monster_client.solve_captcha(recaptcha2request)

    responses = await solve_captcha()
    return responses['gRecaptchaResponse']

class AirdropRegistrator:
    def __init__(self, account):
        self.account = account
        self.proxy = get_random_proxy(proxy_file)
        self.requestor = SyncRequestor(proxy=self.proxy)
        self.requestor.add_header({
            'Referer': 'https://claim.superformfoundation.org/flow',
        })
        self.storage = WalletStorage()
        self.bearer = None

    def get_tos_message(self):
        url = f'https://claim.superformfoundation.org/api/message/tos?address={self.account.address}'
        return self.requestor.get(url=url)['message']

    def sign_message(self, message):
        signed_message = (web3.eth.account.sign_message(encode_defunct(text=message),
                                                        private_key=self.account.key).signature.hex())
        return signed_message

    def login(self):
        self.requestor.add_header({
            'origin': 'https://claim.superformfoundation.org',
        })

        message = self.get_tos_message()
        signed_message = self.sign_message(message=message)

        url = 'https://claim.superformfoundation.org/api/account/login'
        payload = {
             "address": self.account.address,
             "signature": '0x' + signed_message,
             "chainId": 8453
        }

        response = self.requestor.post(url=url, json=payload)
        self.bearer = response.get('jwtToken')
        if self.bearer:
            return True
        return False

    def get_account_data(self):
        url = 'https://claim.superformfoundation.org/api/account'
        account_data = self.requestor.get(url=url)
        return account_data

    def register(self, captcha_code):
        url = 'https://claim.superformfoundation.org/api/account'
        payload = {
            'captchaCode': captcha_code,
        }

        response = self.requestor.post(url=url, json=payload)
        confirmed = response.get('isConfirmed')
        if confirmed:
            logger.success(f'{self.account.address} registered')
            return response
        else:
            logger.error(f'Could not register - {response}')
            raise


    @staticmethod
    def get_account_points(account_data):
        # {'mainWalletAddress': '0xaea07cbe198520699fb858f24e763cec4f016018', 'walletAddresses': ['0xaea07cbe198520699fb858f24e763cec4f016018'], 'isConfirmed': True, 'emails': [], 'allocation': {'total': '1', 'details': {'evm': {'0xaea07cbe198520699fb858f24e763cec4f016018': {'xp': '0', 'cred': '159308.9558', 'points': '24.61372794', 'piggyHoldings': '0', 'guildPoints': '0', 'piggyDAODonations': '0', 'triedV2': 0, 'tierName': 'Bronze', 'tierImage': 'Bronze Alien'}}, 'email': {}}}}
        return account_data['allocation']['details']['evm'][account_data['mainWalletAddress']]


    async def main_script(self):

        if self.storage.exists(self.account.address):
            account_data = self.storage.get(self.account.address)
            logger.success(f'{self.account.address} already registered')
            logger.success(f'Account points - {self.get_account_points(account_data)}')
            raise BreakTimer()

        if self.login():
            self.requestor.add_header({
                'clq-jwt': self.bearer
            })
            account_data = self.get_account_data()
            already_registered = account_data.get('isConfirmed', False)
            if already_registered:
                logger.success(f'{self.account.address} already registered')
                wallet_data = self.get_account_points(account_data)
                logger.success(f'Account points - {wallet_data}')
                self.storage.add(self.account.address, wallet_data)
                raise BreakTimer()

            captcha_code = await solve_captcha()
            account_data = self.register(captcha_code)
            wallet_data = self.get_account_points(account_data)
            logger.success(f'Account points - {wallet_data}')
            self.storage.add(self.account.address, wallet_data)

async def use_script():
    accounts = load_accounts_from_keys(keys_file)
    total_account = len(accounts)
    logger.info(f"Loaded for {total_account} accounts")

    random.shuffle(accounts)

    for account in accounts:

        random_sleep = random.randint(5, 20)

        bot = AirdropRegistrator(account)
        try:
            await bot.main_script()
        except BreakTimer:
            random_sleep = random.randint(0, 1)
        except Exception as err:
            logger.error(err)

        logger.info(f"Finished account {account.address}. Sleeping for {random_sleep} seconds")
        time.sleep(random_sleep)

if __name__ == '__main__':
    asyncio.run(use_script())
