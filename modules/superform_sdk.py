import random
import time

from loguru import logger
from web3 import Web3
from eth_account.account import ChecksumAddress

from typing import Dict, List, Any

from modules.client import MyClient
from modules.superform_api import SuperFormApi
from eth_account.signers.local import LocalAccount

from utils.helpful_scripts import check_tx_status, approve, send_tx_with_data
from config import superform_router_address, eth_address, bridge_slippage, swap_slippage


class MySuperform(MyClient):
    def __init__(self, account: LocalAccount, base_network_id: int = 3):
        super().__init__(account=account, network_id=base_network_id)
        self.module_name = 'SuperForm'
        self.superform_api = SuperFormApi()
        self.native_balance = self.get_native_balance()

    def _check_if_has_enough_balance(self, amount: float, token_address: ChecksumAddress):
        """
        Checks if token balance is bigger than amount
        :param amount: (float) amount in human-readable format
        :param token_address: token address
        :return: (bool) True if balance is bigger than amount, False if not
        """

        if token_address == Web3.to_checksum_address(eth_address):
            token_balance = self.get_normalize_amount(amount_in_wei=self.native_balance, decimals=18)
        else:
            token_balance = self.get_normalize_amount(amount_in_wei=self.get_token_balance(token_address),
                                                      decimals=self.get_decimals(token_address))

        if token_balance < amount:
            return False
        return True

    def before_vault_operation(self, tx_data: Dict, amount: float | int, token_address: ChecksumAddress,
                               superform_id: str, operation_type: str) -> bool:

        approve_data = tx_data['approvalData']

        if approve_data:
            logger.info('Approving')
            tx_approve_hash = send_tx_with_data(to=approve_data['to'], w3=self.w3, explorer=self.explorer,
                                                account=self.account, eip1559=self.eip1559_support,
                                                data=approve_data['data'], value=int(approve_data['value']))
            if not check_tx_status(w3=self.w3, tx_hash=tx_approve_hash):
                logger.error('Could not approve token spend')
                return False

            time.sleep(random.randint(5, 10))

        # for some reason deposit data from api do not have approve_data, need to do this manually
        if operation_type == 'smart' and not approve_data:
            amount = self.to_wei(number=amount, decimals=self.get_decimals(token_address=token_address))
            if not approve(account=self.account, w3=self.w3, token_address=token_address,
                           spender=superform_router_address,
                           explorer=self.explorer, eip1559=self.eip1559_support, amount=amount):
                logger.error('Could not approve token spend')
                return False

            time.sleep(random.randint(5, 10))

        sim_data = {
            'user_address': self.address,
            'superform_id': superform_id,
            'amount_in': amount,
            'type': operation_type,
            'override_state': True,
            'include_approval': True,
            'retain_4626': False,
        }

        simulations = self.superform_api.get_simulation(sim_data)['data']
        for simulation in simulations:
            if 'success' not in simulation.keys() or not simulation['success']:
                logger.error(f'Simulation error {simulation}. Would not make tx correctly')
                return False

        sim_router_data = {
            'user_address': self.address,
            'chain_id': self.chain_id,
            'tx_data': tx_data['data'],
            'value': tx_data['value'],
            'is_router': True
        }

        router_simulation = self.superform_api.get_router_simulation(request_data=sim_router_data)['data']
        if 'success' not in router_simulation.keys() or not router_simulation['success']:
            logger.error(f'Router simulation error {router_simulation}. Would not make operation correctly')
            return False

        return True

    def deposit_single_vault(self, vault_id: str, amount: float, token_address: str | ChecksumAddress = eth_address) \
            -> bool:
        """
        Makes deposit to the selected vault
        :param vault_id: vault_id, e.g. - pxOqM7dFwI2Abt-yTv4jC
        :param amount: (float) amount to deposit in human-readable format
        :param token_address: token to deposit, default is ETH
        :return: True if success, False if not
        """

        token_address = Web3.to_checksum_address(token_address)

        logger.info(f'Depositing {amount} of {token_address} to vault {vault_id}')

        if not self._check_if_has_enough_balance(amount=amount, token_address=token_address):
            raise ValueError(f'Deposit amount {amount} of {token_address} is bigger than balance')

        deposit_params = {
            'user_address': self.address,
            'from_token_address': token_address,
            'from_chain_id': self.chain_id,
            'amount_in': amount,
            'refund_address': self.address,
            'vault_id': vault_id,
            'bridge_slippage': bridge_slippage,
            'swap_slippage': swap_slippage,
            'route_type': 'output',
            'is_part_of_multivault': False,
            'force': int(time.time()) + 300000,
        }

        calculate_dep = self.superform_api.calculate_user_deposit(deposit_params)
        dep_tx_data = self.superform_api.start_deposit(calculate_dep)

        if not self.before_vault_operation(tx_data=dep_tx_data, amount=amount, token_address=token_address,
                                           superform_id=calculate_dep['in']['superFormId'], operation_type='smart'):
            logger.error('Could not make prepare for deposit')
            return False

        tx_hash = send_tx_with_data(to=dep_tx_data['to'], w3=self.w3, explorer=self.explorer, account=self.account,
                                    eip1559=self.eip1559_support, data=dep_tx_data['data'],
                                    value=int(dep_tx_data['value']))

        if check_tx_status(w3=self.w3, tx_hash=tx_hash):
            logger.success('Deposited')
            return True
        return False

    def withdraw_single_vault(self, vault_id: str, withdraw_percent: int = 100,
                              token_address: str | ChecksumAddress = eth_address) -> bool:
        """
        Makes withdrawal from vault
        :param vault_id: vault_id, e.g. - pxOqM7dFwI2Abt-yTv4jC
        :param withdraw_percent: (int) percent of position to be withdrew, default is 100%
        :param token_address: token to withdrew, default is ETH.
            WARNING, withdrawal in ETH may not go through due to Superform design, in this case use WETH instead
        :return: True if success, False if not
        """

        token_address = Web3.to_checksum_address(token_address)

        logger.info(f'Withdrawing {withdraw_percent} percent from vault {vault_id}')

        user_portfolio = self.get_portfolio()
        if vault_id not in user_portfolio.keys():
            logger.info('Do not have deposit in this vault')
            return True

        user_data_in_vault = user_portfolio[vault_id]
        if withdraw_percent == 100:
            amount_to_withdraw = int(user_data_in_vault['superposition_balance'])
        else:
            amount_to_withdraw = int(int(user_data_in_vault['superposition_balance']) / 100 * withdraw_percent)

        # Superposition is represented by number with 18 decimals, we do not want withdrew dust
        if amount_to_withdraw < 100:
            logger.warning('Probably already withdrew. Would not make withdrew of dust position')
            return True

        params = {
            'user_address': self.address,
            'refund_address': self.address,
            'vault_id': vault_id,
            'bridge_slippage': bridge_slippage,
            'swap_slippage': swap_slippage,
            'route_type': 'output',
            'to_token_address': token_address,
            'to_chain_id': self.chain_id,
            'superpositions_amount_in': amount_to_withdraw,
            'superpositions_chain_id': user_data_in_vault['chain id'],
            'is_part_of_multivault': False,
            'force': int(time.time()) + 300000,
            'is_erc20': user_data_in_vault['is_erc20'],
            'retain_4626': 'false',

        }

        calculate_withdraw = self.superform_api.calculate_user_withdrawal(params)
        withdraw_tx_data = self.superform_api.start_withdrawal(calculate_withdraw)

        if not self.before_vault_operation(tx_data=withdraw_tx_data, token_address=token_address,
                                           superform_id=calculate_withdraw['in']['superFormId'],
                                           amount=amount_to_withdraw, operation_type='withdrawal'):
            logger.error('Could not make prepare for withdrawal')
            return False

        tx_hash = send_tx_with_data(to=withdraw_tx_data['to'], w3=self.w3, explorer=self.explorer, account=self.account,
                                    eip1559=self.eip1559_support, data=withdraw_tx_data['data'],
                                    value=int(withdraw_tx_data['value']))

        if check_tx_status(w3=self.w3, tx_hash=tx_hash):
            logger.success('Withdrew')
            return True
        return False

    def get_portfolio(self) -> Dict[Any, Dict[str, Any]]:
        """
        :return: Account portfolio - {'Vault_id': {'usd amount': '', 'chain id': 8453, 'superposition_balance': '', 'is_erc20': False}}
        """
        raw_portfolio = self.superform_api.get_portfolio(address=self.address)
        result = {}
        if raw_portfolio['superpositions']:
            for superpositions in raw_portfolio['superpositions']:
                result[superpositions['vault']['id']] = {
                    'usd amount': superpositions['superposition_usd_value'],
                    'chain id': superpositions['chain_id'],
                    'superposition_balance': superpositions['superposition_balance'],
                    'is_erc20': superpositions['is_erc20'],
                }
        return result

    def get_user_safari_points(self, season: int) -> Dict[Any, Dict[str, Any]]:
        """
        Return the data for safari season
        :param season: (int) Safari season number
        :return: Safari season data - {'user_address': '0x...', 'current': {'tournament_rank': , 'tvl': , 'xp': , 'boost': 2}, 'previous': None}
        """
        return self.superform_api.get_safari_points(self.address, season=season)

    def get_claimable_user_safari_rewards(self, season: int) -> List:
        """
        :param season: (int) Safari season number
        :return: The list of safari rewards to claim
        """
        result = []
        rewards = self.superform_api.get_available_rewards(address=self.address, season=season)
        for reward in rewards:
            if reward['status'] == 'claimable':
                result.append(reward)
        return result

    def claim_all_rewards(self, season: int) -> bool:
        """
        Claims all possible rewards for account in particular safari season
        :param season: (int) Safari season number
        :return: True if success, False if not
        """
        logger.info(f'Claiming rewards for season {season}')

        claimable_rewards = self.get_claimable_user_safari_rewards(season=season)
        if len(claimable_rewards) == 0:
            logger.info('No rewards for claim')
            return True

        params = {
            'tournamentID': season,
            'user': self.address,
        }

        claim_tx_data = self.superform_api.start_claim_rewards(request_data=params)
        tx_hash = send_tx_with_data(to=claim_tx_data['to'], w3=self.w3, explorer=self.explorer, account=self.account,
                                    eip1559=self.eip1559_support, data=claim_tx_data['transactionData'])

        if check_tx_status(w3=self.w3, tx_hash=tx_hash):
            logger.success('Claimed')
            return True
        return False

    def get_rewards(self) -> Dict[Any, Dict[str, Any]]:
        """
        Returns all account rewards from provided liquidity
        :return: Dict in format - {'total_usd_value_claimable': 0, 'total_usd_value_accruing': 0, 'claimable': None, 'accruing': [{'reward_type': 'token', 'token': {'contract_address': '0xA88594D404727625A9437C3f886C7643872296AE', 'decimals': 18, 'id': 0, 'image': 'https://static.debank.com/image/mobm_token/logo_url/0x511ab53f793683763e5a8829738301368a2411e3/b82e97dd371cfdacb522ffebd7840729.png', 'name': 'WELL', 'symbol': 'WELL', 'price_usd': 0.011851379565617413}, 'reward_name': 'Protocol Reward', 'amount': '0', 'usd_value': 0, 'chain_id': 8453, 'rewards_id': 'pxOqM7dFwI2Abt-yTv4jC', 'source_type': 'vault'}]}
        """
        return self.superform_api.get_rewards(address=self.address)
