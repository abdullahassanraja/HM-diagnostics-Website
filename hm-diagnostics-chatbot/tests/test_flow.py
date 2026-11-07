from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.models.schemas import normalize_phone


def send(client, session=None, message='', action=None, consent=False, **extra):
    response = client.post('/api/chat', json={'session_id': session, 'message': message, 'action': action, 'consent': consent, **extra})
    assert response.status_code == 200, response.text
    return response.json()


def review_request(client):
    result = send(client, action='book'); token = result['session_id']
    assert result['state'] == 'consent'
    result = send(client, token, action='consent', consent=True)
    assert result['state'] == 'name'
    for message in ['Demo Visitor', '03001234567', 'CBC', (datetime.now(ZoneInfo('Asia/Karachi')).date() + timedelta(days=1)).isoformat(), '14:30']:
        result = send(client, token, message)
    result = send(client, token, action='skip')
    assert result['state'] == 'review'
    return result


def appointment_payload(review, confirmed=True):
    return {'session_id': review['session_id'], 'confirmation_token': review['confirmation_token'], 'idempotency_key': review['idempotency_key'], 'confirmed': confirmed}


@pytest.mark.parametrize('number', ['03001234567', '+923001234567', '923001234567', '00923001234567', '0300-1234567', '۰۳۰۰۱۲۳۴۵۶۷'])
def test_mobile_normalization(number): assert normalize_phone(number) == '+923001234567'


@pytest.mark.parametrize('number', ['123', '+12025550123', '031234', '030012345678', '0512340199', '<script>'])
def test_invalid_mobile(number):
    with pytest.raises(ValueError): normalize_phone(number)


def test_consent_required_before_contact_collection(client):
    result = send(client, action='book'); sid = result['session_id']
    assert send(client, sid, 'Demo Visitor')['state'] == 'consent'
    assert send(client, sid, action='consent', consent=False)['state'] == 'consent'
    assert not client.app.state.sessions.get(sid).fields.get('patient_name')


def test_full_booking_and_idempotent_retries(client, provider, memory):
    result = review_request(client)
    assert result['summary']['phone'] == '+923001234567'
    payload = appointment_payload(result)
    first = client.post('/api/appointments', json=payload)
    second = client.post('/api/appointments', json=payload)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert first.json()['status'] == 'Pending' and first.json()['demo']
    assert 'NOT been sent to the clinic' in first.json()['message']
    assert len(memory.records) == 1
    assert not provider.contexts  # Booking PII never enters provider routing.
    assert not client.app.state.sessions.get(result['session_id']).fields


def test_confirmation_and_matching_request_required(client, memory):
    review = review_request(client); payload = appointment_payload(review, False)
    assert client.post('/api/appointments', json=payload).status_code == 400
    payload.update(confirmed=True, idempotency_key=str(uuid4()))
    assert client.post('/api/appointments', json=payload).status_code == 409
    assert not memory.records


def test_past_date_and_bad_time_rejected(client):
    result=send(client,action='book'); sid=result['session_id']
    for message,action,consent in [('', 'consent',True),('Demo Visitor',None,False),('03001234567',None,False),('CBC',None,False)]: send(client,sid,message,action,consent)
    assert send(client,sid,'2000-01-01')['state']=='date'
    tomorrow=(datetime.now(ZoneInfo('Asia/Karachi')).date()+timedelta(days=1)).isoformat()
    assert send(client,sid,tomorrow)['state']=='time'
    assert send(client,sid,'25:99')['state']=='time'


def test_start_again_and_cancel_clear_contact_state(client):
    review=review_request(client); sid=review['session_id']
    again=send(client,sid,action='book')
    assert again['state']=='consent'
    assert not client.app.state.sessions.get(sid).fields.get('phone')
    send(client,sid,action='cancel')
    assert client.app.state.sessions.get(sid).fields == {}


def test_personal_information_never_reaches_llm(client,provider):
    for text in ['My name is Ali and my phone is 03001234567, CBC price?', 'I have pain and my report shows a problem', 'my email is patient@example.com, MRI?']:
        result=send(client,message=text)
        assert not result['provider']
    assert not provider.contexts
    result=send(client,message='CBC price')
    assert result['provider']=='gemini'
    assert 'DEMO' in result['reply']
    context=str(provider.contexts[-1])
    assert '03001234567' not in context and 'patient@example.com' not in context
    assert 'CBC price' not in context  # Not even the raw public visitor question is forwarded.


def test_unknown_prices_and_preparation_not_invented(client):
    response=send(client,message='What is the price of an unknown-xyz test?')
    # Generic prices are always labelled demo; no arbitrary price is generated.
    assert 'reception' in response['reply'] and 'DEMO' not in response['reply']
    response=send(client,message='Do I need fasting for MRI?')
    assert 'No test-specific preparation is verified' in response['reply']
    assert '8 hours' not in response['reply']


def test_urgent_message_avoids_provider(client,provider):
    result=send(client,message='severe chest pain and cannot breathe')
    assert 'emergency' in result['reply'] and not provider.contexts


def test_urdu_and_session_expiry(client):
    response=send(client,message='پتہ کہاں ہے؟',language='ur')
    assert 'پتہ' in response['reply'] and 'Islamabad' in response['reply']
    client.app.state.sessions.get(response['session_id']).expires_at=0
    assert client.post('/api/chat',json={'session_id':response['session_id'],'message':'hello'}).status_code==401
