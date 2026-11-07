import hashlib
import re
import time
from collections import defaultdict, deque

from starlette.responses import JSONResponse

from app.config import Settings

SENSITIVE_PATTERN = re.compile(r'(?:\b(?:\+?92|0092|0)?3\d[\d\s()\-]{8,16}\b|\b\d{5}-?\d{7}-?\d\b|[\w.+-]+@[\w.-]+\.[a-z]{2,}|\b(?:cnic|passport|credit card|my name is|patient name|i am named)\b)', re.I)
MEDICAL_PATTERN = re.compile(r'\b(?:diagnos\w*|prescrib\w*|dosage|symptoms?|pain|fever|vomit\w*|dizz\w*|cannot breathe|can.t breathe|bleeding|suicide|overdose|my report|my results|my child has|i have|i feel|i am suffering)\b|درد|بخار|تشخیص|علامات|نسخہ|سانس|خودکشی', re.I)
URGENT_PATTERN = re.compile(r'\b(?:severe chest pain|cannot breathe|can.t breathe|unconscious|severe bleeding|overdose|suicid\w*)\b|بے ہوش|شدید درد|خودکشی', re.I)


def sensitive_text(text: str) -> bool:
    return bool(SENSITIVE_PATTERN.search(text) or MEDICAL_PATTERN.search(text))


def scheduling_notes(text: str) -> str:
    if len(text) > 240 or sensitive_text(text) or re.search(r'\d{12,}', re.sub(r'[ -]', '', text)):
        raise ValueError('Please use scheduling notes only. Do not include medical details, identity numbers or payment information.')
    if any(ord(char) < 32 and char not in '\n\t' for char in text):
        raise ValueError('Please use plain scheduling notes.')
    return text.strip()


class SecurityMiddleware:
    """Bounded ASGI body buffering; never log request bodies or session tokens."""
    def __init__(self, app, settings: Settings):
        self.app, self.settings = app, settings
        self.buckets: dict[str, deque] = defaultdict(deque)

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http': return await self.app(scope, receive, send)
        headers = dict(scope.get('headers', []))
        origin = headers.get(b'origin', b'').decode('latin1').rstrip('/')
        allowed = self.settings.origins + ([self.settings.public_base_url.rstrip('/')] if self.settings.public_base_url else [])
        if scope['path'].startswith('/api/') and origin and origin not in allowed:
            return await JSONResponse({'detail': 'Origin not allowed.'}, status_code=403)(scope, receive, send)
        if scope['path'].startswith('/api/') and scope['method'] == 'POST':
            if self.settings.rate_limit_enabled:
                key = hashlib.sha256(str(scope.get('client', ('unknown',))[0]).encode()).hexdigest()
                now = time.monotonic()
                # Bound memory even for clients rotating IP addresses.
                if len(self.buckets) > 10000:
                    self.buckets = defaultdict(deque, {k: v for k, v in self.buckets.items() if v and v[-1] > now - 60})
                if len(self.buckets) >= 10000 and key not in self.buckets:
                    return await JSONResponse({'detail': 'Reception is busy. Please try again shortly.'}, 429)(scope, receive, send)
                bucket = self.buckets[key]
                while bucket and bucket[0] <= now - 60: bucket.popleft()
                if len(bucket) >= self.settings.rate_limit_per_minute:
                    return await JSONResponse({'detail': 'Please wait a minute before sending more requests.'}, 429, headers={'Retry-After': '60'})(scope, receive, send)
                bucket.append(now)
            chunks, size = [], 0
            while True:
                message = await receive()
                if message['type'] == 'http.disconnect': return
                body = message.get('body', b''); size += len(body)
                if size > self.settings.max_request_bytes:
                    return await JSONResponse({'detail': 'Message too large.'}, 413)(scope, receive, send)
                chunks.append(body)
                if not message.get('more_body', False): break
            complete = b''.join(chunks)
            delivered = False
            original_receive = receive
            async def replay():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {'type': 'http.request', 'body': complete, 'more_body': False}
                return await original_receive()
            receive = replay
        async def secure_send(message):
            if message['type'] == 'http.response.start':
                message['headers'] = list(message.get('headers', [])) + [(b'x-content-type-options', b'nosniff'), (b'cache-control', b'no-store'), (b'referrer-policy', b'no-referrer')]
            await send(message)
        return await self.app(scope, receive, secure_send)
