import warnings
from curl_cffi import requests
from abc import ABC, abstractmethod

from requestor.utils import async_retry, sync_retry, get_default_headers

IMPERSONATE = requests.BrowserType.chrome124
warnings.filterwarnings('ignore', module='curl_cffi')

class Requestor(ABC):
    def __init__(self):
        self.session = None

    @abstractmethod
    def create_session(self) -> None:
        """Create appropriate session type (sync/async)"""
        pass

    def update_headers(self, new_headers: dict) -> None:
        self.session.headers.update(new_headers)

    def add_header(self, add_headers: dict) -> None:
        current_header = self.get_headers()
        current_header.update(add_headers)
        self.update_headers(current_header)

    def get_headers(self) -> dict:
        return self.session.headers

    def update_proxy(self, new_proxy: dict) -> None:
        self.session.proxies.update(new_proxy)

    def delete_all_cookies(self):
        self.session.cookies.clear()

    def delete_all_headers(self):
        self.session.headers.clear()

    def get_proxy(self) -> dict:
        return self.session.proxies

    def set_cookies(self, cookies) -> None:
        for name, value in cookies.items():
            self.session.cookies.set(name, value)

    def get_cookies(self) -> requests.cookies.CookieJar:
        return self.session.cookies

    @classmethod
    def _handle_response(cls, resp_raw, acceptable_statuses=None, resp_handler=None, with_text=False):
        if acceptable_statuses and len(acceptable_statuses) > 0:
            if resp_raw.status_code not in acceptable_statuses:
                raise Exception(f'Bad status code [{resp_raw.status_code}]: Response = {resp_raw.text}')
        try:
            if with_text:
                return resp_raw.text if resp_handler is None else resp_handler(resp_raw.text)
            else:
                return resp_raw.json() if resp_handler is None else resp_handler(resp_raw.json())
        except Exception as e:
            raise Exception(f'{str(e)}: Status = {resp_raw.status_code}')


class SyncRequestor(Requestor):
    def __init__(self, proxy: dict = None, custom_headers: dict = None, custom_cookies: dict = None):
        super().__init__()

        self.create_session()
        self.update_headers(custom_headers) if custom_headers else self.update_headers(get_default_headers())
        proxy and self.update_proxy(proxy)
        custom_cookies and self.set_cookies(custom_cookies)

    def create_session(self):
        self.session = requests.Session()

    def close(self):
        self.session.close()

    def get(self, url, acceptable_statuses=None, resp_handler=None, with_text=False, raw=False, **kwargs):
        return self.request('GET', url, acceptable_statuses, resp_handler, with_text, raw, **kwargs)

    def post(self, url, acceptable_statuses=None, resp_handler=None, with_text=False, raw=False, **kwargs):
        return self.request('POST', url, acceptable_statuses, resp_handler, with_text, raw, **kwargs)

    def put(self, url, acceptable_statuses=None, resp_handler=None, with_text=False, raw=False, **kwargs):
        return self.request('PUT', url, acceptable_statuses, resp_handler, with_text, raw, **kwargs)

    def request(self, method, url, acceptable_statuses=None, resp_handler=None, with_text=False,
                      raw=False, **kwargs):
        if 'timeout' not in kwargs:
            kwargs.update({'timeout': 30})

        resp = self._raw_request(method, url, **kwargs)
        if raw:
            return resp
        return self._handle_response(resp, acceptable_statuses, resp_handler, with_text)

    @sync_retry
    def _raw_request(self, method, url, **kwargs):
        match method.lower():
            case 'get':
                resp = self.session.get(url, **kwargs)

            case 'post':
                resp = self.session.post(url, **kwargs)
            case unexpected:
                raise Exception(f'Wrong request method: {unexpected}')
        return resp

class AsyncRequestor(Requestor):
    def __init__(self, proxy: dict = None, custom_headers: dict = None, custom_cookies: dict = None):
        super().__init__()

        self.create_session()
        self.update_headers(custom_headers) if custom_headers else self.update_headers(get_default_headers())
        proxy and self.update_proxy(proxy)
        custom_cookies and self.set_cookies(custom_cookies)

    def create_session(self):
        self.session = requests.AsyncSession(impersonate=IMPERSONATE)

    async def close(self):
        await self.session.close()

    async def get(self, url, acceptable_statuses=None, resp_handler=None, with_text=False, raw=False, **kwargs):
        return await self.request('GET', url, acceptable_statuses, resp_handler, with_text, raw, **kwargs)

    async def post(self, url, acceptable_statuses=None, resp_handler=None, with_text=False, raw=False, **kwargs):
        return await self.request('POST', url, acceptable_statuses, resp_handler, with_text, raw, **kwargs)

    async def request(self, method, url, acceptable_statuses=None, resp_handler=None, with_text=False,
                      raw=False, **kwargs):
        if 'timeout' not in kwargs:
            kwargs.update({'timeout': 60})

        resp = await self._raw_request(method, url, **kwargs)
        if raw:
            return resp
        return self._handle_response(resp, acceptable_statuses, resp_handler, with_text)

    @async_retry
    async def _raw_request(self, method, url, **kwargs):
        match method.lower():
            case 'get':
                resp = await self.session.get(url, **kwargs)
            case 'post':
                resp = await self.session.post(url, **kwargs)
            case unexpected:
                raise Exception(f'Wrong request method: {unexpected}')
        return resp
