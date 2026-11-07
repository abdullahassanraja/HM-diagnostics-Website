import re
import unicodedata
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class ChatInput(StrictModel):
    message: str = Field(default='', max_length=1000)
    session_id: str | None = Field(default=None, min_length=32, max_length=100, pattern=r'^[A-Za-z0-9_-]+$')
    action: str | None = Field(default=None, max_length=40)
    consent: bool = False
    language: Literal['en', 'ur'] = 'en'


class QuickAction(StrictModel):
    label: str
    action: str


class ChatOutput(StrictModel):
    session_id: str
    reply: str
    state: str
    quick_actions: list[QuickAction] = Field(default_factory=list)
    demo_mode: bool
    language: Literal['en', 'ur'] = 'en'
    confirmation_token: str | None = None
    idempotency_key: str | None = None
    summary: dict[str, str] | None = None
    sources: list[str] = Field(default_factory=list)
    provider: str | None = None


class AppointmentInput(StrictModel):
    session_id: str = Field(min_length=32, max_length=100, pattern=r'^[A-Za-z0-9_-]+$')
    confirmation_token: str = Field(min_length=32, max_length=100, pattern=r'^[A-Za-z0-9_-]+$')
    idempotency_key: UUID
    confirmed: bool


class AppointmentRecord(StrictModel):
    request_id: UUID
    created_at: datetime
    patient_name: str
    phone: str
    service: str
    preferred_date: date
    preferred_time: str
    notes: str = ''
    status: Literal['Pending'] = 'Pending'
    source: Literal['Website Chatbot'] = 'Website Chatbot'

    @field_validator('phone')
    @classmethod
    def valid_phone(cls, value: str) -> str:
        return normalize_phone(value)


class AppointmentOutput(StrictModel):
    request_id: UUID
    status: Literal['Pending'] = 'Pending'
    saved: bool
    demo: bool
    message: str


def normalize_phone(value: str) -> str:
    value = ''.join(str(unicodedata.digit(char)) if char.isdecimal() else char for char in value)
    value = re.sub(r'[\s()\-]', '', value.strip())
    if value.startswith('0092'):
        value = '+' + value[2:]
    if re.fullmatch(r'03[0-9]{9}', value):
        value = '+92' + value[1:]
    elif re.fullmatch(r'923[0-9]{9}', value):
        value = '+' + value
    if not re.fullmatch(r'\+923[0-9]{9}', value):
        raise ValueError('Enter a Pakistani mobile number, for example 03XXXXXXXXX.')
    return value
