import json

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.google_sheets import MemoryAppointmentStore
from app.services.provider_base import ProviderError


class FakeProvider:
    def __init__(self, name='gemini', error=None):
        self.name, self.error, self.available = name, error, True
        self.contexts = []

    async def generate(self, context):
        self.contexts.append(context)
        if self.error: raise self.error
        return json.dumps({'record_ids': [r['id'] for r in context['allowed_records']]})


@pytest.fixture
def settings():
    return Settings(_env_file=None, demo_mode=True, demo_data_enabled=True,
                    rate_limit_enabled=False, llm_max_retries=0, keep_alive_enabled=False)


@pytest.fixture
def provider(): return FakeProvider()


@pytest.fixture
def memory(): return MemoryAppointmentStore(30)


@pytest.fixture
def client(settings, provider, memory):
    with TestClient(create_app(settings, providers=[provider], store=memory)) as client:
        yield client
