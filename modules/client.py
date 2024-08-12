import random
import json

from pathlib import Path
from web3 import Web3

from web3.contract import Contract
from eth_account.signers.local import LocalAccount
from eth_account.account import ChecksumAddress
from utils.helpful_scripts import get_network_by_chain_id, get_native, get_balance, get_decimals


class MyClient:
    def __init__(self, account: LocalAccount, network_id: int):
        """
        Basic client class
        :param account: LocalAccount instance
        :param network_id: number according to chain_name dict in config
        """
        self.account: LocalAccount = account
        self.address: ChecksumAddress = self.account.address

        self.network_id = network_id
        self.network = get_network_by_chain_id(self.network_id)
        self.provider = random.choice(self.network.rpc)
        self.eip1559_support = self.network.eip1559_support
        self.token = self.network.token
        self.explorer = self.network.explorer
        self.chain_id = self.network.chain_id
        self.rpc = random.choice(self.network.rpc)
        self.w3 = Web3(Web3.HTTPProvider(self.rpc))

    def get_native_balance(self) -> int:
        """
        :return: (int) Balance of native coin
        """
        return get_native(w3=self.w3, wallet=self.address)

    def get_token_balance(self, token_address: ChecksumAddress) -> int:
        """
        :param token_address: ChecksumAddress, address of the token
        :return: (int) Balance of token
        """
        return get_balance(wallet=self.address, w3=self.w3, token_address=token_address, symbol='token')

    def to_wei(self, number: int | float | str, decimals: int = 18) -> int:
        """
        Convert number to amount in wei. Adds decimals
        :param number: number to be converted
        :param decimals: decimals, by default - 18
        :return: long int number
        """
        unit_name = {
            18: 'ether',
            6: 'mwei'
        }[decimals]

        return self.w3.to_wei(number=number, unit=unit_name)

    def get_decimals(self, token_address: ChecksumAddress) -> int:
        """
        Returns token decimals of the following erc20 token
        :param token_address: (ChecksumAddress) token address
        :return: (int) decimals of the token
        """
        return get_decimals(w3=self.w3, token_address=token_address)

    def get_normalize_amount(self, amount_in_wei: int, decimals: int = None, token_address: ChecksumAddress = None) -> (
            float):
        """
        Returns humanreadable decimal contract
        :param decimals:
        :param token_address: token address
        :param amount_in_wei: amount in wei
        :return: normal amount
        """
        if not decimals and not token_address:
            raise ValueError("should provide decimals of token address")
        if not decimals:
            decimals = self.get_decimals(token_address)
        return float(amount_in_wei / 10 ** decimals)

    def get_contract(self, contract_address: ChecksumAddress, abi_file_path: str = 'files/abis/erc20.json') -> Contract:
        """
        Returns contract instance
        :param contract_address: contract address
        :param abi_file_path: (optional) abi file path, if not provided erc20 used
        :return: Contract instance
        """
        try:
            return self.w3.eth.contract(
                address=Web3.to_checksum_address(contract_address),
                abi=json.load(Path(abi_file_path).open())['abi']
            )
        except:
            return self.w3.eth.contract(
                address=Web3.to_checksum_address(contract_address),
                abi=json.load(Path(abi_file_path).open())
            )
