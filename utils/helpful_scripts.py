import json
import random
import time
import requests
import functools
import datetime

from sys import stderr
from loguru import logger
from pathlib import Path

from web3 import Account, Web3
from web3.exceptions import BadFunctionCallOutput
from typing import Dict, Any, List
from cryptography.fernet import Fernet
from eth_account.signers.local import LocalAccount
from eth_account.account import ChecksumAddress

from utils.constants import MAX_APPROVAL_INT
from config import tg_token, tg_chat_id, script_name
from utils.networks import *

abi_files = {
    'erc20': 'files/abis/erc20.json',
}


"""
THE LIST OF HELPFUL FUNCTIONS
NOT ALL OF THEM USED IN EVERY PROJECT
"""


def load_logger(file_log):
    # LOGGING SETTING
    logger.remove()
    logger.add(stderr, format="<white>{time:HH:mm:ss}</white> | <level>{level: <8}</level> | <cyan>{line}</cyan> - "
                              "<white>{message}</white>")
    logger.add(file_log + f"{datetime.datetime.now().strftime('%Y%m%d')}.log",
               format="<white>{time:HH:mm:ss}</white> | <level>{level: <8}</level> | <cyan>{line}</cyan> - <white>{"
                      "message}</white>")


def get_token_price(token_name: str, vs_currency: str = 'usd') -> float:
    time.sleep(10)
    url = 'https://api.coingecko.com/api/v3/simple/price'
    params = {'ids': f'{token_name}', 'vs_currencies': f'{vs_currency}'}
    session = requests.Session()
    with session.get(url, params=params) as response:
        if response.status_code == 200:
            try:
                data = response.json()
                return float(data[token_name][vs_currency])
            except:
                raise AttributeError('no such currency on coingecko')
        elif response.status_code == 429:
            logger.error('Coingecko API RateLimit')
            time.sleep(30)
            raise requests.exceptions.ConnectionError(f'Bad request to CoinGecko API: {response.status_code}')


def get_balance(wallet: ChecksumAddress, symbol: str, w3: Web3, token_address: ChecksumAddress = None) -> int:
    if symbol != 'eth':
        if token_address is None:
            logger.error("wrong input")
            raise ValueError

        erc20_contract = w3.eth.contract(token_address, abi=json.load(Path(abi_files['erc20']).open()))
        try:
            balance = erc20_contract.functions.balanceOf(wallet).call()
        except BadFunctionCallOutput:
            balance = "n/a"
        return balance

    else:
        balance = w3.eth.get_balance(wallet)
    return balance


def get_native(wallet: ChecksumAddress, w3: Web3) -> int:
    return get_balance(wallet=wallet, symbol='eth', w3=w3)


def check_tx_status(w3: Web3, tx_hash):
    tx_status = get_tx_status(w3=w3, tx_hash=tx_hash)
    if tx_status != 1:
        return False
    return True


def get_tx_status(w3: Web3, tx_hash) -> int:
    time.sleep(20)
    status_ = None
    tries = 0
    while not status_:
        try:
            status_ = w3.eth.get_transaction_receipt(tx_hash)
        except:
            logger.info('Still trying to get tx status')
            tries += 1
            time.sleep(150)
            if tries == 2:
                status_["status"] = 1
                logger.info('Probably success, but not sure')

    status = status_["status"]
    logger.info(f"Tx status: {status}")

    if status not in [0, 1]:
        raise Exception("could not obtain tx status in 60 seconds")
    else:
        return status


def _create_transaction_params(account: LocalAccount, w3: Web3, eip1559: bool, gas: int = 0, value: int = 0) -> Dict:
    tx_params = {
        "from": account.address,
        "value": value,
        'chainId': w3.eth.chain_id,
        "nonce": w3.eth.get_transaction_count(account.address),
    }

    if eip1559:
        base_fee = int(w3.eth.gas_price * 1.1)

        if w3.eth.chain_id == 324:  # zksync
            max_priority_fee_per_gas = 1_000_000
        elif w3.eth.chain_id == 250:  # Fantom
            max_priority_fee_per_gas = int(base_fee / 4)
        else:
            max_priority_fee_per_gas = w3.eth.max_priority_fee

        if w3.eth.chain_id == 42170:  # Arb Nova
            base_fee = int(base_fee * 1.25)

        if w3.eth.chain_id == 42161:  # Arb
            tx_params['gas'] = random.randint(650_000, 850_000)

        max_fee_per_gas = base_fee + max_priority_fee_per_gas
        tx_params['maxPriorityFeePerGas'] = max_priority_fee_per_gas
        tx_params['maxFeePerGas'] = max_fee_per_gas
        tx_params['type'] = '0x2'

    else:
        if w3.eth.chain_id == 56:  # 'BNB Chain'
            tx_params['gasPrice'] = w3.to_wei(round(random.uniform(1.2, 1.5), 1), 'gwei')
        elif w3.eth.chain_id == 1284:  # 'Moonbeam'
            tx_params['gasPrice'] = int(w3.eth.gas_price * 1.5)
        elif w3.eth.chain_id == 1285:  # 'Moonriver'
            tx_params['gasPrice'] = int(w3.eth.gas_price * 1.5)
        else:
            tx_params['gasPrice'] = w3.eth.gas_price

    if gas != 0:
        tx_params['gas'] = gas

    return tx_params


def send_transaction(raw_tx: Any, w3: Web3, explorer: str, account: LocalAccount, eip1559: bool, gas: int = 0,
                     value: int = 0):
    transaction_params = _create_transaction_params(account=account, w3=w3, eip1559=eip1559, gas=gas, value=value)
    tx = raw_tx.build_transaction(transaction_params)
    if tx['gas'] == 0:
        estimate_gas = int(w3.eth.estimate_gas(tx) * 1.1)
        tx.update({'gas': estimate_gas})
    signed_tx = w3.eth.account.sign_transaction(tx, account.key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    logger.info(f"Tx: {explorer}tx/{tx_hash.hex()}")
    return tx_hash


def send_eth(to: ChecksumAddress, w3: Web3, account: LocalAccount, explorer: str,
             eip1559: bool, value: int = 0, send_max: bool = False):
    if send_max:
        native_balance = get_native(wallet=account.address, w3=w3)
        value = native_balance - 21_000 * (w3.eth.gas_price + w3.eth.max_priority_fee)
    tx = _create_transaction_params(account=account, w3=w3, value=value, eip1559=eip1559)
    tx.update({'to': to})
    tx.update({'gas': 21000})
    if send_max:
        native_balance = get_native(wallet=account.address, w3=w3)
        tx.update({'value': native_balance - 21_000 * (tx['maxFeePerGas'] + tx['maxPriorityFeePerGas'])})
    if w3.eth.chain_id == 324:
        estimate_gas = int(w3.eth.estimate_gas(tx))
        tx.update({'gas': estimate_gas})

    signed_tx = w3.eth.account.sign_transaction(tx, account.key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    logger.info(f"Tx: {explorer}tx/{tx_hash.hex()}")
    return tx_hash


def send_tx_with_data(to: ChecksumAddress, w3: Web3, account: LocalAccount, explorer: str,
                      eip1559: bool, data: str, value: int = 0):
    tx = _create_transaction_params(account=account, w3=w3, value=value, eip1559=eip1559)
    tx.update({'to': to})
    tx.update({'data': data})

    estimate_gas = int(w3.eth.estimate_gas(tx) * 1.05)
    tx.update({'gas': estimate_gas})

    signed_tx = w3.eth.account.sign_transaction(tx, account.key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    logger.info(f"Tx: {explorer}tx/{tx_hash.hex()}")
    return tx_hash


def get_decimals(w3: Web3, token_address: ChecksumAddress) -> int:
    erc20_contract = w3.eth.contract(token_address, abi=json.load(Path(abi_files['erc20']).open()))
    try:
        decimals = erc20_contract.functions.decimals().call()
    except BadFunctionCallOutput:
        decimals = "n/a"
    return decimals


def load_accounts_from_keys(path: str) -> List[LocalAccount]:
    file = Path(path).open()
    return [Account.from_key(line.replace("\n", "")) for line in file.readlines()]


def load_wallets(path: str):
    file = Path(path).open()
    return [line.replace("\n", "") for line in file.readlines()]


def load_accounts_from_keys_encrypted(file_path: str, key_path: str) -> List[LocalAccount]:
    with open(key_path, 'rb') as unlock:
        key = unlock.read()
        f = Fernet(key)
        file = Path(file_path)
        with open(file, 'rb') as encrypted_file:
            encrypted = encrypted_file.read()
            # decrypt the file
            decrypted = f.decrypt(encrypted)
            # return decrypted.decode().split('\n')
            return [Account.from_key(line.replace("\r", "")) for line in decrypted.decode().split('\n')]


def get_network_by_chain_id(chain_id) -> Network:
    return {
        0: ArbitrumRPC,
        1: ArbitrumRPC,
        2: Arbitrum_novaRPC,
        3: BaseRPC,
        4: LineaRPC,
        5: MantaRPC,
        6: PolygonRPC,
        7: OptimismRPC,
        8: ScrollRPC,
        # 9: StarknetRPC,
        10: Polygon_ZKEVM_RPC,
        11: zkSyncEraRPC,
        12: ZoraRPC,
        13: EthereumRPC,
        14: AvalancheRPC,
        15: BSC_RPC,
        16: MoonbeamRPC,
        17: HarmonyRPC,
        18: TelosRPC,
        19: CeloRPC,
        20: GnosisRPC,
        21: CoreRPC,
        22: TomoChainRPC,
        23: ConfluxRPC,
        24: OrderlyRPC,
        25: HorizenRPC,
        26: MetisRPC,
        27: AstarRPC,
        28: OpBNB_RPC,
        29: MantleRPC,
        30: MoonriverRPC,
        31: KlaytnRPC,
        32: KavaRPC,
        33: FantomRPC,
        34: AuroraRPC,
        35: CantoRPC,
        36: DFK_RPC,
        37: FuseRPC,
        38: GoerliRPC,
        39: MeterRPC,
        40: OKX_RPC,
        41: ShimmerRPC,
        42: TenetRPC,
        43: XPLA_RPC,
        44: LootChainRPC,
        45: ZKFairRPC,
        46: BeamRPC,
        47: InEVM_RPC,
        48: RaribleRPC,

        49: SepoliaRPC,
        50: MumbaiRPC,
    }[chain_id]


def get_random_word(amount, separator="") -> str:
    word_site = "https://www.mit.edu/~ecprice/wordlist.10000"
    response = requests.get(word_site)
    words = response.content.splitlines()
    result = [random.choice(words).decode("utf-8").capitalize() for _ in range(0, amount)]
    return separator.join(result)


def get_gas_base():
    try:
        w3 = Web3(Web3.HTTPProvider('https://mainnet.base.org'))
        gas_price = w3.eth.gas_price
        gwei = w3.from_wei(gas_price, 'gwei')
        return gwei
    except Exception as error:
        logger.error(error)


def max_gas(max_gwei, alternative_flow=None):
    """Decorator that checks current gas"""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            gas = get_gas_base()
            if gas >= max_gwei:
                if alternative_flow:
                    logger.info(f'Current GWEI: {gas} > {max_gwei}. Using gassless function')
                    return alternative_flow()
                logger.info(f'Current GWEI: {gas} > {max_gwei}. Sleeeping.....')
                return
            else:
                return func(*args, **kwargs)

        return wrapper

    return decorator


def _is_approved(account: LocalAccount, w3: Web3, token_addr: ChecksumAddress, amount: int, spender: ChecksumAddress) \
        -> bool:
    erc20_contract = w3.eth.contract(token_addr, abi=json.load(Path(abi_files['erc20']).open()))
    approved_amount = erc20_contract.functions.allowance(account.address, spender).call()
    return approved_amount >= amount


def approve(account: LocalAccount, w3: Web3, token_address: ChecksumAddress, spender: ChecksumAddress,
            explorer, eip1559, amount: int = MAX_APPROVAL_INT) \
        -> bool:
    if _is_approved(account, w3, token_address, amount, spender):
        return True

    logger.info(f"Approving {amount} of {token_address}")
    erc20_contract = w3.eth.contract(token_address, abi=json.load(Path(abi_files['erc20']).open()))
    raw_tx = erc20_contract.functions.approve(spender, MAX_APPROVAL_INT)
    return check_tx_status(w3=w3, tx_hash=send_transaction(raw_tx=raw_tx, w3=w3, account=account,
                                                           explorer=explorer, eip1559=eip1559))


def catch_errors(sleep_times):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as err:
                exception_type = type(err)
                if exception_type in sleep_times:
                    sleep_time = random.randint(*sleep_times[exception_type])
                else:
                    sleep_time = random.randint(*sleep_times['other_exception'])
                logger.error(f'Something went wrong with script {script_name} - {exception_type.__name__}: {err}, Sleeping for {sleep_time} seconds')
                if len(tg_token) > 0 and len(tg_chat_id) > 0:
                    send_error_message(message=f"Caught {exception_type.__name__}: {err} ", script=script_name)
                time.sleep(sleep_time)
        return wrapper
    return decorator


def send_error_message(message: str, script: str):
    send_text = 'https://api.telegram.org/bot' + tg_token + '/sendMessage?chat_id=' + \
                tg_chat_id + f'&parse_mode=Markdown&text=Script: {script}. {message}'
    requests.get(send_text)
