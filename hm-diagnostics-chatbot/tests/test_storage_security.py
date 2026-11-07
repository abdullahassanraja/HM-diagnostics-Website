from datetime import datetime,timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.models.schemas import AppointmentRecord
from app.services.clinic_service import ClinicService
from app.services.google_sheets import HEADERS,GoogleSheetsStore,StorageError,safe_cell
from app.services.keep_alive import KeepAlive
from test_flow import appointment_payload,review_request


class BrokenStore:
    async def save(self,record):raise StorageError('never expose raw credentials')
    def cleanup(self):pass


def test_storage_error_does_not_claim_saved(settings):
    with TestClient(create_app(settings,providers=[],store=BrokenStore())) as client:
        review=review_request(client)
        response=client.post('/api/appointments',json=appointment_payload(review))
        assert response.status_code==503
        assert 'could not verify' in response.json()['detail']
        assert 'credentials' not in response.text
        assert client.app.state.sessions.get(review['session_id']).stage=='review'


async def test_sheets_adapter_raw_and_existing_id(settings,monkeypatch):
    record=AppointmentRecord(request_id=uuid4(),created_at=datetime.now(ZoneInfo('Asia/Karachi')),patient_name='Demo Visitor',phone='03001234567',service='CBC',preferred_date=datetime.now().date()+timedelta(days=1),preferred_time='14:30')
    saved=set();appends=[]
    def handler(request):
        if request.method=='POST':
            import json
            body=json.loads(request.content);appends.append(body)
            assert request.url.params['valueInputOption']=='RAW'
            saved.add(str(record.request_id))
            return httpx.Response(200,json={'updates':{'updatedRows':1}})
        if 'A1' in str(request.url):return httpx.Response(200,json={'values':[HEADERS]})
        return httpx.Response(200,json={'values':[[value] for value in saved]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        store=GoogleSheetsStore(settings,client)
        async def token():return 'mock-token'
        monkeypatch.setattr(store,'_token',token)
        await store.save(record);await store.save(record)
    assert len(appends)==1
    assert appends[0]['values'][0][8:] == ['Pending','Website Chatbot']
    assert safe_cell('=HYPERLINK("evil")').startswith("'")


def test_health_no_external_calls(client,provider,memory):
    assert client.get('/health').json()=={'status':'ok'}
    assert not provider.contexts and not memory.records


def test_public_config_and_kb_no_secrets(client):
    text=client.get('/api/config').text+client.get('/api/clinic-info').text
    assert 'api_key' not in text and 'private_key' not in text and 'service_account' not in text
    assert client.get('/api/config').json()['demo_mode'] is True


def test_demo_prices_can_be_disabled(settings):
    kb=ClinicService(settings.knowledge_path,False)
    assert not [r for r in kb.allowed_records() if r.status=='demo']
    assert not kb.find('cbc price','prices')


def test_unknown_fields_and_size_origin_rate_limits(settings):
    settings.rate_limit_enabled=True;settings.rate_limit_per_minute=2;settings.max_request_bytes=1024
    with TestClient(create_app(settings,providers=[])) as client:
        assert client.post('/api/chat',headers={'Origin':'https://evil.example'},json={'message':'hello'}).status_code==403
        assert client.post('/api/chat',json={'message':'x'*2000}).status_code==413
        assert client.post('/api/chat',json={'message':'hello','cnic':'12345-1234567-1'}).status_code==422
        assert client.post('/api/chat',json={'message':'hi'}).status_code==429


def test_sensitive_notes_rejected(client):
    from test_flow import send
    review=review_request(client)
    session=client.app.state.sessions.get(review['session_id']);session.stage='notes'
    result=send(client,session.id,'My chest pain is worse and my CNIC is 12345-1234567-1')
    assert result['state']=='notes'
    assert 'scheduling notes only' in result['reply']


async def test_keepalive_start_once_cancel_and_health_ping(settings):
    settings.keep_alive_enabled=True;settings.public_base_url='https://example.onrender.com'
    called=[]
    def handler(request):called.append(str(request.url));return httpx.Response(200,json={'status':'ok'})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        keep=KeepAlive(settings,client);keep.start();task=keep.task;keep.start();assert keep.task is task
        await keep.ping_once();assert called==['https://example.onrender.com/health']
        await keep.stop();assert keep.task is None and task.cancelled()


def test_no_memory_storage_in_live_mode(settings):
    from app.config import Settings
    with pytest.raises(ValueError):Settings(_env_file=None,demo_mode=False,appointment_storage='memory')
