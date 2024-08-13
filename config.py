from utils.constants import BreakTimer

script_name = 'Superform'


log_file = './logs/superform'
keys_file = './files/keys'
wallets_file = './files/wallets'

minimum_balance_left = 0.02

sleeping_time = {
    'default': (30, 60),
    BreakTimer: (1, 3),
    ConnectionError: (300, 500),
    'other_exception': (50, 150),
}


superform_router_address = '0xa195608C2306A26f727d5199D5A382a4508308DA'
eth_address = '0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE'
weth_address = '0x4200000000000000000000000000000000000006'

morpho_well_eth_vault_id = 'pxOqM7dFwI2Abt-yTv4jC'   # Base Moonwell Flagship ETH

bridge_slippage = 10  # 0.1%
swap_slippage = 10  # 0.1%

# add tg token if you want to send error messages somewhere
tg_token = ''
tg_chat_id = ''
