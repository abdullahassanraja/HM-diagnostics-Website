import secrets
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request

from app.models.schemas import AppointmentInput, AppointmentOutput, AppointmentRecord
from app.services.google_sheets import StorageError

router = APIRouter(prefix='/api')


@router.post('/appointments', response_model=AppointmentOutput)
async def submit(payload: AppointmentInput, request: Request) -> AppointmentOutput:
    state = request.app.state
    session = state.sessions.get(payload.session_id)
    async with session.lock:
        if not payload.confirmed: raise HTTPException(400, 'Please explicitly confirm the reviewed details before submitting.')
        if not secrets.compare_digest(payload.confirmation_token, session.confirmation_token) or str(payload.idempotency_key) != session.request_id:
            raise HTTPException(409, 'This confirmation no longer matches your request. Review the details again.')
        if session.receipt: return AppointmentOutput.model_validate(session.receipt)
        if session.stage != 'review' or not session.consent: raise HTTPException(409, 'Complete the consent and review steps first.')
        fields = dict(session.fields); fields.pop('kind', None)
        try:
            state.conversation.validate_date(fields['preferred_date'])
            desired = datetime.fromisoformat(fields['preferred_date'] + 'T' + fields['preferred_time']).replace(tzinfo=ZoneInfo(state.settings.timezone))
            if desired < datetime.now(ZoneInfo(state.settings.timezone)): raise ValueError('Please choose a future preferred date and time. Start again to edit your request.')
            record = AppointmentRecord(request_id=UUID(session.request_id), created_at=datetime.now(ZoneInfo(state.settings.timezone)), **fields)
        except (ValueError, KeyError):
            raise HTTPException(422, 'Please review the request and choose a future preferred date and time. Start again to change details.') from None
        try: await state.store.save(record)
        except StorageError:
            raise HTTPException(503, 'We could not verify that your request was saved. Retry this same request or call reception. Your appointment is not confirmed.') from None
        demo = state.settings.demo_mode
        message = ('Thank you—your demo request has been received in temporary memory only. It has NOT been sent to the clinic and is not a confirmed appointment. Is there anything else I can help you with?' if demo else 'Thank you—your request has been received and is Pending. Reception still needs to confirm availability; this is not a confirmed appointment. Is there anything else I can help you with?')
        output = AppointmentOutput(request_id=record.request_id, status='Pending', saved=True, demo=demo, message=message)
        session.receipt = output.model_dump(mode='json'); session.stage = 'submitted'
        session.fields.clear()  # PII is no longer needed for conversation state after submission.
        return output
