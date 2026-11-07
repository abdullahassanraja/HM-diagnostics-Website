from fastapi import APIRouter, Request

from app.models.schemas import ChatInput, ChatOutput

router = APIRouter(prefix='/api')


@router.post('/chat', response_model=ChatOutput)
async def chat(payload: ChatInput, request: Request) -> ChatOutput:
    session = request.app.state.sessions.get(payload.session_id, create=True)
    async with session.lock:
        return await request.app.state.conversation.respond(session, payload)


@router.get('/config')
async def public_config(request: Request) -> dict:
    from app.core.conversation import ACTIONS, WELCOME
    settings = request.app.state.settings
    return {'app_name': settings.app_name, 'greeting': WELCOME, 'demo_mode': settings.demo_mode,
            'demo_data_enabled': settings.demo_data_enabled,
            'storage': 'ephemeral_demo' if settings.demo_mode and settings.appointment_storage == 'memory' else 'clinic_google_sheet',
            'session_ttl_minutes': settings.session_ttl_minutes,
            'quick_actions': [{'label': label, 'action': action} for label, action in ACTIONS],
            'reception_phone': request.app.state.clinic.knowledge.contact_number,
            'privacy_notice': 'Your booking details are not sent to AI providers. Do not share medical reports, CNIC or payment details. Demo mode accepts fictional details only.'}


@router.get('/clinic-info')
async def clinic_info(request: Request) -> dict:
    return request.app.state.clinic.public_info()
