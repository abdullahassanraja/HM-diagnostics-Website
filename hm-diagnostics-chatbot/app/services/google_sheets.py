"""Single-worker, retry-safe Sheets submission. No appointment files on disk."""
import asyncio
import json
import re
import time
from typing import Protocol

import httpx
from google.auth.transport.requests import Request
from google.oauth2 import service_account

from app.config import Settings
from app.models.schemas import AppointmentRecord

HEADERS = ['Request ID', 'Created At', 'Patient Name', 'Phone Number', 'Test / Service', 'Preferred Date', 'Preferred Time', 'Notes', 'Status', 'Source']


class StorageError(Exception):
    pass


class AppointmentStore(Protocol):
    async def save(self, record: AppointmentRecord) -> None: ...
    def cleanup(self) -> None: ...


class MemoryAppointmentStore:
    """Explicit demo storage: ephemeral, TTL-limited, never represented as a real booking."""
    def __init__(self, retention_minutes: int):
        self.ttl = retention_minutes * 60
        self.records: dict[str, tuple[float, AppointmentRecord]] = {}

    def cleanup(self) -> None:
        now = time.monotonic()
        for key in [k for k, (expiry, _) in self.records.items() if expiry <= now]: self.records.pop(key, None)

    async def save(self, record: AppointmentRecord) -> None:
        self.cleanup()
        if len(self.records) >= 5000 and str(record.request_id) not in self.records:
            raise StorageError('Demo request capacity reached. Please try again later.')
        self.records.setdefault(str(record.request_id), (time.monotonic() + self.ttl, record))


def safe_cell(value: str) -> str:
    # RAW prevents formula evaluation in Sheets; prefix also helps with later CSV exports.
    if re.fullmatch(r'\+923\d{9}', value): return value
    return "'" + value if value.lstrip().startswith(('=', '+', '-', '@', '\t', '\r')) else value


class GoogleSheetsStore:
    def __init__(self, settings: Settings, client: httpx.AsyncClient):
        self.settings, self.client = settings, client
        self.lock = asyncio.Lock()
        self.credentials = None

    def cleanup(self) -> None:
        pass  # Retention of the shared spreadsheet is managed by authorized clinic staff.

    async def _token(self) -> str:
        try:
            if not self.settings.google_sheet_id or not self.settings.google_service_account_json.get_secret_value():
                raise StorageError()
            if self.credentials is None:
                info = json.loads(self.settings.google_service_account_json.get_secret_value())
                if info.get('token_uri') != 'https://oauth2.googleapis.com/token': raise StorageError()
                self.credentials = service_account.Credentials.from_service_account_info(info, scopes=['https://www.googleapis.com/auth/spreadsheets'])
            if not self.credentials.valid:
                request = Request()
                def bounded_request(*args, **kwargs):
                    kwargs['timeout'] = 8
                    return request(*args, **kwargs)
                await asyncio.wait_for(asyncio.to_thread(self.credentials.refresh, bounded_request), timeout=12)
            return self.credentials.token
        except Exception:
            raise StorageError('Appointment storage is temporarily unavailable.') from None

    async def save(self, record: AppointmentRecord) -> None:
        from urllib.parse import quote
        async with self.lock:
            token = await self._token()
            sheet = "'" + self.settings.google_sheet_name.replace("'", "''") + "'"
            base = 'https://sheets.googleapis.com/v4/spreadsheets/' + quote(self.settings.google_sheet_id, safe='') + '/values/'
            headers = {'Authorization': 'Bearer ' + token}
            try:
                header = await self.client.get(base + quote(sheet + '!A1:J1', safe=''), headers=headers, timeout=8)
                header.raise_for_status()
                if header.json().get('values', [[]])[0] != HEADERS: raise StorageError('Spreadsheet headers are not configured.')
                ids = await self.client.get(base + quote(sheet + '!A2:A', safe=''), headers=headers, timeout=8)
                ids.raise_for_status()
                if any(row and row[0] == str(record.request_id) for row in ids.json().get('values', [])): return
                values = [str(record.request_id), record.created_at.isoformat(), record.patient_name, record.phone,
                          record.service, record.preferred_date.isoformat(), record.preferred_time, record.notes, record.status, record.source]
                response = await self.client.post(base + quote(sheet + '!A:J', safe='') + ':append', headers=headers,
                    params={'valueInputOption': 'RAW', 'insertDataOption': 'INSERT_ROWS'},
                    json={'values': [[safe_cell(v) for v in values]]}, timeout=10)
                response.raise_for_status()
                if response.json().get('updates', {}).get('updatedRows') != 1: raise StorageError()
            except (httpx.HTTPError, ValueError, KeyError, IndexError, StorageError):
                # An ambiguous append is not retried automatically. A visitor retry uses the
                # same request ID and checks column A before another append.
                raise StorageError('Could not verify that your request was saved. Please retry the same request or contact reception.') from None
