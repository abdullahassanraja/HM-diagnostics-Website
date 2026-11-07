import json
from typing import Protocol

import httpx


class ProviderError(Exception):
    def __init__(self, category: str, retry_after: float = 0):
        super().__init__(category)  # Never attach response text, request headers or user input.
        self.category = category
        self.retry_after = retry_after

    @property
    def transient(self) -> bool:
        return self.category in {'timeout', 'rate_limit', 'unavailable', 'invalid_response'}


class Provider(Protocol):
    name: str
    available: bool

    async def generate(self, context: dict) -> str: ...


def check_response(response: httpx.Response) -> None:
    if response.status_code in (401, 403):
        raise ProviderError('authentication')
    if response.status_code == 429:
        try: retry_after = min(300.0, max(0.0, float(response.headers.get('retry-after', '0'))))
        except ValueError: retry_after = 0
        raise ProviderError('rate_limit', retry_after)
    if response.status_code >= 500:
        raise ProviderError('unavailable')
    if response.status_code >= 400:
        raise ProviderError('configuration')


def serialize_context(context: dict) -> str:
    return json.dumps(context, ensure_ascii=False, separators=(',', ':'))
