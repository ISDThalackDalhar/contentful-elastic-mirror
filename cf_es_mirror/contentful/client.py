import requests
from requests.adapters import HTTPAdapter
from urllib3.exceptions import ConnectTimeoutError

from contentful.client import Client as BaseClient
from contentful.errors import RateLimitExceededError


class Client(BaseClient):
    max_retries = 3

    def _http_get(self, url, query):
        """
        Performs the HTTP GET Request.
        """
        if not self.authorization_as_header:
            query.update({'access_token': self.access_token})

        response = None

        self._normalize_query(query)

        kwargs = {
            'params': query,
            'headers': self._request_headers(),
            'timeout': self.timeout_s
        }

        if self._has_proxy():
            kwargs['proxies'] = self._proxy_parameters()

        with requests.Session() as s:
            _url = self._url(url)
            s.mount(_url, HTTPAdapter(max_retries=self.max_retries))
            try:
                response = s.get(
                    _url,
                    **kwargs
                )
            except ConnectTimeoutError:
                response = requests.Response()
                response.status_code = 500

            if response.status_code == 429:
                raise RateLimitExceededError(response)
        return response
