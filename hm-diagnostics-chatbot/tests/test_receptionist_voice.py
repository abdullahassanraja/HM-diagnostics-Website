from test_flow import send


def test_price_answer_offers_honest_callback_without_auto_booking(client, memory):
    result = send(client, message='CBC price')
    assert 'Happy to help' in result['reply']
    assert 'DEMO' in result['reply'] and 'not a confirmed HM fee' in result['reply']
    assert 'confirm the current fee and availability' in result['reply']
    assert result['state'] == 'idle' and not memory.records
    assert result['quick_actions'][0]['action'] == 'callback'
    yes = send(client, result['session_id'], 'yes please')
    assert yes['state'] == 'consent'  # Agreement to a next step is not data consent.
    assert not client.app.state.sessions.get(yes['session_id']).consent


def test_service_interest_is_offered_only_after_consent_and_can_be_selected(client):
    result = send(client, message='Do you offer MRI?')
    assert 'requesting a visit' in result['reply']
    sid = result['session_id']
    assert send(client, sid, 'yes')['state'] == 'consent'
    send(client, sid, action='consent', consent=True)
    send(client, sid, 'Demo Visitor')
    service = send(client, sid, '03001234567')
    assert service['state'] == 'service'
    assert 'MRI / CT scan' in service['reply']
    assert any(action['action'] == 'use_interest' for action in service['quick_actions'])
    assert send(client, sid, action='use_interest')['state'] == 'date'
    assert client.app.state.sessions.get(sid).fields['service'] == 'MRI / CT scan'


def test_decline_and_goodbye_do_not_push_a_booking(client, provider):
    result = send(client, message='Do you offer MRI?'); sid = result['session_id']
    decline = send(client, sid, 'No thanks, not now')
    assert decline['state'] == 'idle' and 'take your time' in decline['reply']
    assert all(a['action'] != 'book' for a in decline['quick_actions'])
    goodbye = send(client, sid, 'bye')
    assert goodbye['state'] == 'idle' and 'Allah Hafiz' in goodbye['reply']
    assert not goodbye['quick_actions']


def test_thank_you_does_not_make_next_yes_a_booking(client):
    result = send(client, message='Do you offer MRI?'); sid = result['session_id']
    assert 'very welcome' in send(client, sid, 'thank you')['reply']
    clarify = send(client, sid, 'yes')
    assert clarify['state'] == 'idle' and 'what would you like help with' in clarify['reply']


def test_no_sales_followup_for_urgent_or_medical_questions(client):
    urgent = send(client, message='severe chest pain and cannot breathe')
    assert not urgent['quick_actions']
    medical = send(client, message='I have fever')
    assert all(action['action'] != 'book' for action in medical['quick_actions'])


def test_urdu_closing_and_welcome(client):
    welcome = send(client, message='سلام', language='ur')
    assert 'خوش آمدید' in welcome['reply']
    goodbye = send(client, welcome['session_id'], 'اللہ حافظ', language='ur')
    assert 'اپنا خیال' in goodbye['reply'] and not goodbye['quick_actions']
