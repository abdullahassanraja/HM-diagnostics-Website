import asyncio
import json
from datetime import datetime,timedelta
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models.schemas import AppointmentRecord
from app.services.clinic_service import ClinicService
from app.services.google_sheets import HEADERS,GoogleSheetsStore,StorageError
from test_flow import send


def test_hot_reload_single_price_amount_and_verified_toggle(settings,tmp_path):
    data=json.loads(settings.knowledge_path.read_text(encoding='utf-8'))
    path=tmp_path/'knowledge.json';path.write_text(json.dumps(data),encoding='utf-8')
    kb=ClinicService(path,True)
    first=next(r for r in kb.allowed_records() if r.id=='demo-cbc')
    assert '700' in kb.render([first],'en')
    for r in data['records']:
        if r['id']=='demo-cbc':r['amount']=975;r['status']='verified';r['source_url']='https://hmdiagnosticsandclinics.com/'
    path.write_text(json.dumps(data),encoding='utf-8')
    # Ensure metadata changes even on filesystems with coarse timestamp resolution.
    import os
    os.utime(path,ns=(path.stat().st_atime_ns,path.stat().st_mtime_ns+1_000_000_000))
    updated=next(r for r in kb.allowed_records() if r.id=='demo-cbc')
    assert kb.render([updated],'en')=='Complete blood count (CBC): PKR 975.'
    assert 'DEMO' not in kb.render([updated],'en')


def test_contact_fields_and_unknown_price(client):
    assert '0334-6333044' in send(client,action='reception')['reply']
    result=send(client,message='price for a test-not-in-the-file')
    assert 'reception' in result['reply'] and 'PKR' not in result['reply']


def test_partial_doctor_search_and_plain_greeting(client):
    result=send(client,message='Dr Amna')
    assert 'Amna Rashid' in result['reply']
    assert 'Assalam-o-Alaikum' in send(client,message='hello')['reply']


def test_no_pii_in_operational_logs(client,caplog):
    send(client,message='My name is Demo Person and my phone is 03001234567')
    send(client,message='CBC price')
    assert 'Demo Person' not in caplog.text and '03001234567' not in caplog.text


def test_demo_cannot_write_to_live_sheet():
    with pytest.raises(ValueError):Settings(_env_file=None,demo_mode=True,appointment_storage='google_sheets')


async def test_ambiguous_sheets_append_retry_checks_id(settings,monkeypatch):
    record=AppointmentRecord(request_id=uuid4(),created_at=datetime.now(ZoneInfo('Asia/Karachi')),patient_name='Demo Visitor',phone='03001234567',service='CBC',preferred_date=datetime.now().date()+timedelta(days=1),preferred_time='14:30')
    saved=set();attempts=[]
    def handler(request):
        if request.method=='POST':
            attempts.append(request);saved.add(str(record.request_id));raise httpx.ReadTimeout('response lost')
        if 'A1' in str(request.url):return httpx.Response(200,json={'values':[HEADERS]})
        return httpx.Response(200,json={'values':[[value] for value in saved]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        store=GoogleSheetsStore(settings,client)
        async def token():return 'mock'
        monkeypatch.setattr(store,'_token',token)
        with pytest.raises(StorageError):await store.save(record)
        await store.save(record)
    assert len(attempts)==1
