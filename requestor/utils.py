import asyncio
import random
import time

MAX_TRIES = 5

USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
SEC_CH_UA = '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"'
SEC_CH_UA_PLATFORM = '"Windows"'

def get_default_headers():
    return {
        'accept': '*/*',
        'accept-encoding': 'gzip, deflate, br',
        'accept-language': 'en-US,en;q=0.9',
        'sec-ch-ua': SEC_CH_UA,
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': SEC_CH_UA_PLATFORM,
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': USER_AGENT,
    }

def async_retry(async_func):
    async def wrapper(*args, **kwargs):
        tries, delay = MAX_TRIES, 1.5
        while tries > 0:
            try:
                return await async_func(*args, **kwargs)
            except Exception:
                tries -= 1
                if tries <= 0:
                    raise
                await asyncio.sleep(delay)

                delay *= 2
                delay += random.uniform(0, 1)
                delay = min(delay, 10)

    return wrapper

def sync_retry(sync_func):
    def wrapper(*args, **kwargs):
        tries, delay = MAX_TRIES, 15
        while tries > 0:
            try:
                return sync_func(*args, **kwargs)
            except Exception:
                tries -= 1
                if tries <= 0:
                    raise
                time.sleep(delay)

                delay *= 2
                delay += random.uniform(0, 1)
                delay = min(delay, 10)

    return wrapper
