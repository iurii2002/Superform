import json
import random
import time

from pathlib import Path

import requests
from loguru import logger
from web3 import Web3
from eth_abi import encode

from modules.client import MyClient
from modules.superform_api import SuperFormApi
from eth_account.signers.local import LocalAccount

from other.helpful_scripts import send_transaction, check_tx_status, approve, send_eth, send_tx_with_data
from other.constants import BreakTimer
from config import super_form_contract_address

abi_files = {
    'SuperformRouter': 'files/abis/superform/SuperformRouter.json',
    'erc20.json': 'files/abis/erc20.json'
}


class MySuperform(MyClient):
    def __init__(self, account: LocalAccount, base_network_id: int = 3):
        super().__init__(account=account, network_id=base_network_id)
        self.api = SuperFormApi()
        self.module_name = 'SuperForm'
        self.native_balance = self.get_native_balance()

    def deposit_single_vault(self, vault_id: str, amount: float,
                             token_address='0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE'):
        logger.info(f'Depositing {amount} to vault {vault_id}')

        if token_address == '0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE':
            if self.get_normalize_amount(amount_in_wei=self.native_balance, decimals=18) < amount:
                raise ValueError(f'Deposit amount {amount} is bigger than balance')

        params = {
            'user_address': self.address,
            'from_token_address': token_address,
            'from_chain_id': self.chain_id,
            'amount_in': amount,
            'refund_address': self.address,
            'vault_id': vault_id,
            'bridge_slippage': 10,
            'swap_slippage': 10,
            'route_type': 'output',
            'is_part_of_multivault': False,
            'force': int(time.time()) + 300000,
        }

        calculate_dep = self.api.calculate_user_deposit(params)
        dep_tx_data = self.api.start_deposit(calculate_dep)

        if token_address != '0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE':
            approve_amount = self.to_wei(amount, decimals=self.get_decimals(token_address=
                                                                            Web3.to_checksum_address(token_address)))
            approve(account=self.account, w3=self.w3, token_address=Web3.to_checksum_address(token_address),
                    spender=super_form_contract_address['SuperformRouter'],
                    explorer=self.explorer, eip1559=self.eip1559_support, amount=approve_amount)

            time.sleep(random.randint(5, 10))

            sim_value = str(self.to_wei(amount, self.get_decimals(token_address)))
            router_sim_value = sim_value
            sim_data = {
                'user_address': self.address,
                'superform_id': calculate_dep['in']['superFormId'],
                'amount_in': sim_value,
                'type': 'smart',
                'override_state': True,
                'include_approval': True,
                'retain_4626': False,
            }

            simulations = self.api.get_simulation(sim_data)['data']

            for simulation in simulations:
                if 'success' not in simulation.keys() or not simulation['success']:
                    logger.error(f'Simulation error {simulation}')
                    return

        sim_router_data = {
            'user_address': self.address,
            'chain_id': self.chain_id,
            'tx_data': dep_tx_data['data'],
            'value': dep_tx_data['value'],
            'is_router': True,
        }

        router_simulation = self.api.get_router_simulation(request_data=sim_router_data)['data']

        if 'success' not in router_simulation.keys() or not router_simulation['success']:
            logger.error(f'Simulation error {router_simulation}')
            return

        tx_hash = send_tx_with_data(to=dep_tx_data['to'], w3=self.w3, explorer=self.explorer, account=self.account,
                                    eip1559=self.eip1559_support, data=dep_tx_data['data'],
                                    value=int(dep_tx_data['value']))
        if tx_hash:
            return True
        return False

    #
    #     def deposit_vault_crosschain(self):
    #         # singleXChainSingleVaultDeposit(tuple req_)
    #         pass

    def withdraw_single_vault(self, vault_id: str, withdraw_percent: int,
                              token_address='0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE'):
        logger.info(f'Withdrawing {withdraw_percent} percent from vault {vault_id}')

        user_portfolio = self.get_portfolio()
        if vault_id not in user_portfolio.keys():
            logger.info('Do not have deposit in this vault')
            return

        user_data_in_vault = user_portfolio[vault_id]
        if withdraw_percent == 100:
            amount_to_withdraw = int(user_data_in_vault['superposition_balance'])
        else:
            amount_to_withdraw = int(int(user_data_in_vault['superposition_balance']) / 100 * withdraw_percent)

        if amount_to_withdraw < 100:
            logger.warning('Probably already withdrew')
            return

        params = {
            'user_address': self.address,
            'refund_address': self.address,
            'vault_id': vault_id,
            'bridge_slippage': 10,
            'swap_slippage': 10,
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

        calculate_withdraw = self.api.calculate_user_withdrawal(params)
        withdraw_tx_data = self.api.start_withdrawal(calculate_withdraw)

        approve_data = withdraw_tx_data['approvalData']
        if approve_data:
            logger.info('Approving position NFT')
            tx_approve_hash = send_tx_with_data(to=approve_data['to'], w3=self.w3, explorer=self.explorer,
                                                account=self.account,
                                                eip1559=self.eip1559_support, data=approve_data['data'],
                                                value=int(approve_data['value']))
            if not tx_approve_hash:
                raise InterruptedError('Could not approve token spend')

        time.sleep(random.randint(5, 10))

        sim_data = {
            'user_address': self.address,
            'superform_id': calculate_withdraw['in']['superFormId'],
            'amount_in': amount_to_withdraw,
            'type': 'withdrawal',
            'override_state': True,
            'include_approval': True,
            'retain_4626': 'false',
        }

        simulations = self.api.get_simulation(sim_data)['data']
        for simulation in simulations:
            if 'success' not in simulation.keys() or not simulation['success']:
                logger.error(f'Simulation error {simulation}')
                return

        sim_router_data = {
            'user_address': self.address,
            'chain_id': self.chain_id,
            'tx_data': withdraw_tx_data['data'],
            'value': withdraw_tx_data['value'],
            'is_router': True
        }

        router_simulation = self.api.get_router_simulation(request_data=sim_router_data)['data']
        if 'success' not in router_simulation.keys() or not router_simulation['success']:
            logger.error(f'Simulation error {router_simulation}')
            return

        logger.info('Withdrawing position')
        tx_hash = send_tx_with_data(to=withdraw_tx_data['to'], w3=self.w3, explorer=self.explorer, account=self.account,
                                    eip1559=self.eip1559_support, data=withdraw_tx_data['data'],
                                    value=int(withdraw_tx_data['value']))
        if tx_hash:
            return True
        return False

    def get_portfolio(self):
        raw_portfolio = self.api.get_portfolio(address=self.address)
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

    def get_user_safari_points(self):
        return self.api.get_safari_points(self.address)

    def get_user_safari_rewards(self, season: int):
        return self.api.get_available_rewards(address=self.address, season=season)

    def get_claimable_user_safari_rewards(self, season: int):
        result = []
        rewards = self.get_user_safari_rewards(season=season)
        for reward in rewards:
            if reward['status'] == 'claimable':
                result.append(reward)
        return result

    def claim_all_rewards(self, season: int):
        logger.info(f'Claiming rewards for season {season}')

        claimable_rewards = self.get_claimable_user_safari_rewards(season=season)
        if len(claimable_rewards) == 0:
            raise ValueError('No rewards for claim')

        params = {
            'tournamentID': season,
            'user': self.address,
        }

        claim_tx_data = self.api.start_claim_rewards(request_data=params)
        tx_hash = send_tx_with_data(to=claim_tx_data['to'], w3=self.w3, explorer=self.explorer, account=self.account,
                                    eip1559=self.eip1559_support, data=claim_tx_data['transactionData'])
        if tx_hash:
            return True
        return False

    def get_rewards(self):
        return self.api.get_rewards(address=self.address)
