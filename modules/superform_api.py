import requests
import urllib.parse

from eth_account.account import ChecksumAddress
from typing import Dict, Optional, List, Tuple
from fake_useragent import UserAgent


class RequestException(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return 'RequestException: %s' % self.message


def _get_headers() -> Dict:
    ua = UserAgent()
    return {
            'Accept': 'application/json',
            'User-Agent': ua.random,
            'Origin': 'https://app.superform.xyz',
            'Referer': 'https://app.superform.xyz/',
           }


def _handle_response(response: requests.Response):
    """Internal helper for handling API responses from the server.
    Raises the appropriate exceptions when necessary; otherwise, returns the
    response.
    """
    if not (200 <= response.status_code < 300):
        raise RequestException('Invalid Response: %s' % response.text)
    try:
        return response.json()
    except:
        raise RequestException('Invalid Response: %s' % response.text)


class SuperFormApi:
    def __init__(self, headers=None):
        self.endpoint = 'https://api.superform.xyz/'
        self.headers = headers if headers else _get_headers()
        self.session = self._init_session()

    """
    BASE METHODS
    """

    def _init_session(self) -> requests.Session:
        """
        Internal function that creates session instance for further requests
        :return: (requests.Session)
        """
        session = requests.session()
        session.headers.update(self.headers)
        return session

    def _create_api_uri(self, path: str, params: Dict = None) -> str:
        """
        Creates uri for api request
        :param path: (str) Path added to standard endpoint in self.endpoint
        :param params: (option) (Dict) additional parameters, if we need to add ={parameter} to uri
        :return: (str) uri
        """
        if params:
            return self.endpoint + path + urllib.parse.urlencode(params)
        return self.endpoint + path

    def _request(self, method: str, uri: str, **kwargs):
        """
        Makes request
        :param method: (str) get, put, option request method
        :param uri: (str) uri string for request
        :param kwargs: (dict) additional arguments to request
        :return: returns request response from _handle_response function
        """
        if method.lower() not in ['get', 'post', 'option']:
            raise RequestException('Used wrong request method')
        self.response = getattr(self.session, method)(uri, **kwargs)
        return _handle_response(self.response)

    """
    GENERAL METHODS
    """

    def get_supported_chains(self) -> List[Dict]:
        """
        :return: The list of supported chains with all data
        """
        path = 'supported/chains'
        uri = self._create_api_uri(path)
        return self._request(method='get', uri=uri)

    def get_admin(self) -> Dict:
        """
        :return: Details about superform protocol
        """
        path = 'admin/config'
        uri = self._create_api_uri(path)
        return self._request(method='get', uri=uri)

    def get_contract_deployment_address(self) -> Dict:
        """
        :return: The list  of deployed contracts in different chains
        """
        path = 'deployment'
        uri = self._create_api_uri(path)
        return self._request(method='get', uri=uri)

    """
    PROTOCOL METHODS
    """

    def get_all_protocols(self) -> List[Dict]:
        """
        :return: list of all protocols with details
        """
        path = f'protocols'
        uri = self._create_api_uri(path)
        return self._request(method='get', uri=uri)

    def get_protocol_data(self, protocol_vanity_url: str) -> Dict:
        """
        :param protocol_vanity_url: protocol identifier, could be obtained from get_all_protocols[protocol][vanity_url]
        :return: Protocol data
        """
        path = f'protocol?vanity_url={protocol_vanity_url}'
        uri = self._create_api_uri(path)
        return self._request(method='get', uri=uri)

    def get_protocol_vaults(self, protocol_vanity_url: str, chain: str = None) -> List[Dict]:
        """
        :param protocol_vanity_url: protocol identifier, could be obtained from get_all_protocols[protocol][vanity_url]
        :param chain: (opt) filter by specific chain, e.g. - "Ethereum", "Base"
        :return: List of vaults with full details
        """
        protocol_id = self.get_protocol_data(protocol_vanity_url)['id']
        path = f'protocol/{protocol_id}/vaults'
        uri = self._create_api_uri(path)
        response = self._request(method='get', uri=uri)
        if chain:
            return [vault for vault in response if vault['chain']['name'] == chain]
        return response

    """
    VAULT METHODS
    """

    def get_all_vaults(self) -> List[Dict]:
        """
        :return: list of all vaults with details
        """
        path = f'vaults'
        uri = self._create_api_uri(path)
        return self._request(method='get', uri=uri)

    def get_vault_data(self, vault_id: str) -> Dict:
        """
        :param vault_id: Vault_id, e.g. - pxOqM7dFwI2Abt-yTv4jC
        :return: Vault current data
        """
        path = f'vault/{vault_id}?timestamp=false'
        uri = self._create_api_uri(path)
        return self._request(method='get', uri=uri)

    """
    STATS METHODS
    """

    def get_all_vaults_stats(self) -> List[Dict]:
        """
        :return: list of all vault stats with APY and other staff
        """
        path = f'stats/vault/superformStat'
        uri = self._create_api_uri(path)
        return self._request(method='get', uri=uri)

    """
    USER METHODS
    """

    def calculate_user_deposit(self, params: Dict) -> Dict:
        """
        Calculates the deposit data for tx
        :param params: Dict:
            user_address: (address) self.address
            from_token_address: (address) token address - 0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE for native
            from_chain_id: (int)
            amount_in: (float)
            refund_address: (address) self.address
            vault_id: (str)
            bridge_slippage: (int)
            swap_slippage: (int)
            route_type: (str) - output
            is_part_of_multivault: (bool)
            force: (int) - timestamp
        :return: Internal data to be used to start deposit process
        """
        path = 'deposit/calculate?'
        uri = self._create_api_uri(path, params)
        return self._request(method='get', uri=uri)

    def calculate_user_withdrawal(self, params: Dict) -> Dict:
        """
        Calculates the withdrawal data for tx
        :param params: Dict:
            user_address: (address) self.address
            refund_address: (address) self.address
            vault_id: (str)
            bridge_slippage: (int)
            swap_slippage: (int)
            route_type: (str) - output
            to_token_address: (address) token address - 0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE for native
            from_chain_id: (int)
            supershares_amount_in: (int)
            is_part_of_multivault: (bool)
            supershares_chain_id: (int)
            force: (int) - timestamp
        :return: Internal data to be used to start withdrawal process
        """
        path = 'withdraw/calculate?'
        uri = self._create_api_uri(path, params)
        return self._request(method='get', uri=uri)

    def start_deposit(self, request_data) -> Dict:
        """
        returns data for deposit tx
        :param request_data: data from calculate_user_deposit function
        :return: Dict
            to: Tx destination
            method: contract method used, e.g - "singleDirectSingleVaultDeposit"
            data: Tx data
            value: Tx value
            valueUSD: usd equivalent of tx data
            originalFeeUSD: ""
            discountPercent: ""
            approvalData: ""
        """
        path = 'deposit/start'
        uri = self._create_api_uri(path)
        return self._request(method='post', uri=uri, json=request_data)

    def start_withdrawal(self, request_data: Dict) -> Dict:
        """
        returns data for withdrawal tx
        :param request_data: data from calculate_user_withdrawal function
        :return: Dict
            to: Tx destination
            method: contract method used, e.g - "singleDirectSingleVaultDeposit"
            data: Tx data
            value: Tx value
            valueUSD: usd equivalent of tx data
            originalFeeUSD: ""
            discountPercent: ""
            approvalData: ""
        """
        path = 'withdraw/start'
        uri = self._create_api_uri(path)
        return self._request(method='post', uri=uri, json=request_data)

    def get_simulation(self, params: Dict) -> Dict:
        """
        Simulate deposit into Superform
        :param params: Dict
            'user_address': self.address,
            'superform_id': calculate_dep['in']['superFormId'],
            'amount_in': amount,
            'type': 'smart',
            'override_state': True,
            'include_approval': True,
            'retain_4626': False,
        :return: Result of simulation operation, e.g. -
            'data': [{}...],
            'message': "Successfully ran simulation: ",
            'status': 200
        """
        path = 'simulation/superform?'
        uri = self._create_api_uri(path, params)
        return self._request(method='get', uri=uri)

    def get_router_simulation(self, request_data: Dict) -> Dict:
        """
        Simulate deposit transaction
        :param request_data: Dict
            'user_address': self.address,
            'chain_id': self.chain_id,
            'tx_data': tx_data['data'],
            'value': tx_data['value'],
            'is_router': True
        :return: Result of simulated transaction, e.g.-
            'data': {id: "https://dashboard.tenderly.co/su",…}
            'message': "Successfully ran simulation"
            'status': 200
        """
        path = 'simulation/router'
        uri = self._create_api_uri(path)
        return self._request(method='post', uri=uri, json=request_data)

    def get_rewards(self, address: str | ChecksumAddress) -> Dict:
        """
        :param address: Account address
        :return: Rewards of address, e.g. - {'total_usd_value_claimable': 0, 'total_usd_value_accruing': 0, 'claimable': None, 'accruing': None}
        """
        path = f'protocolRewards/{address}'
        uri = self._create_api_uri(path)
        return self._request(method='get', uri=uri)

    def get_portfolio(self, address: str | ChecksumAddress) -> Dict:
        """
        :param address: Account address
        :return: Portfolio of address, e.g. - {'portfolio_value': '149.9403132725575495', 'superpositions': []}
        """
        path = f'token/superpositions/balances/{address}?fetch_erc20s=true'
        uri = self._create_api_uri(path)
        return self._request(method='get', uri=uri)

    """
    SAFARY METHODS
    """

    def get_safari_points(self, address: str | ChecksumAddress, season: int) -> Dict:
        """
        :param address: Account address
        :param season: (int) Season number
        :return: Information about safari points, e.g. - {'user_address': '0x....', 'current': {'tournament_rank': 30,..}
        """
        path = f'superrewards/tournamentXP/{season}?user={address}'
        uri = self._create_api_uri(path)
        return self._request(method='get', uri=uri)

    def get_safari_tournaments(self) -> List[Dict]:
        """
        :return:  Returns the list of all safari seasons from the beginning
        """
        path = f'superrewards/tournaments'
        uri = self._create_api_uri(path)
        return self._request(method='get', uri=uri)

    def get_live_safari_tournaments(self) -> List[Dict]:
        """
        :return: Returns the list of ACTIVE safari seasons from the beginning
        """
        tournaments = self.get_safari_tournaments()
        return [tournament for tournament in tournaments if tournament['state'] == 'live']

    def get_finished_safari_tournaments(self) -> List[Dict]:
        """
        :return: Returns the list of ENDED safari seasons from the beginning
        """
        tournaments = self.get_safari_tournaments()
        return [tournament for tournament in tournaments if tournament['state'] == 'finished']

    def get_available_rewards(self, address: str | ChecksumAddress, season: int) -> List[Dict]:
        """
        :param address: Account address
        :param season: (int) Season number
        :return: The list of all rewards of the current season with status for particular address - 'status': 'non-claimable' / 'claimed'
        """
        path = f'superrewards/rewards/{season}/{address}'
        uri = self._create_api_uri(path)
        return self._request(method='get', uri=uri)

    def start_claim_rewards(self, request_data: Dict) -> Dict:
        """
        :param request_data: Dict
            'tournamentID': season,
            'user': self.address,
        :return: Data for claim reward tx
        """
        path = f'superrewards/start/claim'
        uri = self._create_api_uri(path)
        return self._request(method='post', uri=uri, json=request_data)
