import asyncio
import secrets
import time
from dataclasses import dataclass, field
from uuid import uuid4

from fastapi import HTTPException


@dataclass
class Session:
    id: str
    expires_at: float
    stage: str = 'idle'
    language: str = 'en'
    consent: bool = False
    fields: dict[str, str] = field(default_factory=dict)
    topics: list[str] = field(default_factory=list)
    confirmation_token: str = ''
    request_id: str = field(default_factory=lambda: str(uuid4()))
    receipt: dict | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def reset(self) -> None:
        self.stage, self.consent = 'idle', False
        self.fields.clear()
        self.confirmation_token = ''
        self.request_id = str(uuid4())
        self.receipt = None


class SessionManager:
    def __init__(self, ttl_minutes: int, max_sessions: int):
        self.ttl, self.max_sessions = ttl_minutes * 60, max_sessions
        self.sessions: dict[str, Session] = {}

    def cleanup(self) -> None:
        now = time.monotonic()
        for key in [key for key, session in self.sessions.items() if session.expires_at <= now]:
            self.sessions.pop(key, None)

    def get(self, token: str | None, create: bool = False) -> Session:
        self.cleanup()
        if token:
            session = self.sessions.get(token)
            if not session: raise HTTPException(401, 'This chat session expired. Start a new chat; no previous booking will be resubmitted.')
            session.expires_at = time.monotonic() + self.ttl
            return session
        if not create: raise HTTPException(401, 'Start a chat session first.')
        if len(self.sessions) >= self.max_sessions: raise HTTPException(503, 'Reception is busy. Please try again shortly.')
        token = secrets.token_urlsafe(32)
        session = Session(token, time.monotonic() + self.ttl)
        self.sessions[token] = session
        return session
