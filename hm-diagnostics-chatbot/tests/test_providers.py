import json

import httpx
import pytest

from app.services.gemini_service import GeminiService
from app.services.groq_service import GroqService
from app.services.llm_router import LLMRouter
from app.services.provider_base import ProviderError
from conftest import FakeProvider

CONTEXT={'allowed_records':[{'id':'location','label':'Location','text':'Public clinic address','status':'verified'}],'prior_topic_ids':[]}


@pytest.mark.asyncio
async def test_gemini_success(settings):
    settings.gemini_enabled=True; settings.gemini_model='configured-model'
    from pydantic import SecretStr
    settings.gemini_api_key=SecretStr('test-key')
    def handler(request):
        assert request.headers['x-goog-api-key']=='test-key'
        assert 'test-key' not in str(request.url)
        return httpx.Response(200,json={'candidates':[{'content':{'parts':[{'text':'{"record_ids":["location"]}'}]}}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider=GeminiService(settings,client)
        selected,name=await LLMRouter([provider],settings).select(CONTEXT)
        assert selected==['location'] and name=='gemini'


@pytest.mark.parametrize('category',['timeout','rate_limit','unavailable','invalid_response'])
async def test_gemini_failure_falls_back_to_groq(settings,category):
    primary=FakeProvider('gemini',ProviderError(category))
    secondary=FakeProvider('groq')
    selected,name=await LLMRouter([primary,secondary],settings).select(CONTEXT)
    assert name=='groq' and selected==['location']
    assert primary.contexts==secondary.contexts


async def test_both_unavailable_and_circuit_breaker(settings):
    primary=FakeProvider('gemini',ProviderError('rate_limit',120));secondary=FakeProvider('groq',ProviderError('authentication'))
    router=LLMRouter([primary,secondary],settings)
    assert await router.select(CONTEXT)==(None,None)
    assert await router.select(CONTEXT)==(None,None)
    assert len(primary.contexts)==len(secondary.contexts)==1


async def test_bounded_retries(settings):
    settings.llm_max_retries=1
    primary=FakeProvider('gemini',ProviderError('timeout'));secondary=FakeProvider('groq')
    assert (await LLMRouter([primary,secondary],settings).select(CONTEXT))[1]=='groq'
    assert len(primary.contexts)==2


@pytest.mark.parametrize('text',['{"record_ids":["made-up-price"]}','{"record_ids":[],"answer":"fake fee"}','not json','{"record_ids":["location"],"extra":"ignore instructions"}'])
def test_unapproved_provider_output_rejected(text):
    with pytest.raises(ProviderError): LLMRouter.validate_output(text,{'location'})


async def test_groq_http_adapter_and_nonretryable_credentials(settings):
    from pydantic import SecretStr
    settings.groq_model='configured-model';settings.groq_api_key=SecretStr('test-key')
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(401,json={'error':'secret raw provider detail'}))) as client:
        with pytest.raises(ProviderError) as error: await GroqService(settings,client).generate(CONTEXT)
        assert error.value.category=='authentication'
        assert 'secret raw' not in str(error.value)


def test_failed_providers_return_grounded_contact_reply(settings):
    from fastapi.testclient import TestClient
    from app.main import create_app
    primary=FakeProvider('gemini',ProviderError('timeout'));secondary=FakeProvider('groq',ProviderError('unavailable'))
    with TestClient(create_app(settings,providers=[primary,secondary])) as client:
        result=client.post('/api/chat',json={'message':'where is your location?'}).json()
        assert '0334-6333044' in result['reply'] and 'temporarily unavailable' in result['reply']
