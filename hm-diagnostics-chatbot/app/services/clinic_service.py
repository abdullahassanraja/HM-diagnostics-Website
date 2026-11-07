"""Small, reloadable JSON knowledge base. No vectors, embeddings or model training."""
import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeRecord(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(pattern=r'^[a-z0-9_-]+$')
    category: Literal['clinic', 'services', 'tests', 'prices', 'preparation', 'faq', 'policy', 'doctors']
    status: Literal['verified', 'demo', 'unverified']
    label: str
    label_ur: str = ''
    text: str
    text_ur: str = ''
    keywords: list[str]
    source_url: str | None = None
    amount: int | None = Field(default=None, ge=0)
    currency: Literal['PKR'] | None = None


class KnowledgeBase(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_version: Literal[1]
    clinic_name: str
    address: str
    contact_number: str
    landline: str
    email: str
    opening_hours: dict[str, str | None]
    reviewed_on: str
    review_note: str
    records: list[KnowledgeRecord]


class ClinicService:
    def __init__(self, path: Path, demo_data_enabled: bool):
        self.path = path
        self.demo_data_enabled = demo_data_enabled
        self._mtime = -1
        self._knowledge: KnowledgeBase | None = None
        self.knowledge  # Fail clearly on invalid configuration at startup.

    @property
    def knowledge(self) -> KnowledgeBase:
        mtime = self.path.stat().st_mtime_ns
        if mtime != self._mtime:
            candidate = KnowledgeBase.model_validate_json(self.path.read_text(encoding='utf-8-sig'))
            ids = [record.id for record in candidate.records]
            if len(ids) != len(set(ids)):
                raise ValueError('Knowledge record IDs must be unique.')
            self._knowledge, self._mtime = candidate, mtime
        assert self._knowledge is not None
        return self._knowledge

    def allowed_records(self) -> list[KnowledgeRecord]:
        return [r for r in self.knowledge.records if r.status == 'verified' or (r.status == 'demo' and self.demo_data_enabled)]

    def find(self, message: str, topic: str | None = None) -> list[KnowledgeRecord]:
        normalized = message.casefold()
        records = self.allowed_records()
        if topic:
            categories = {'tests': {'tests', 'services'}, 'prices': {'prices'}, 'hours': {'clinic'}, 'doctors': {'doctors'}, 'preparation': {'preparation', 'faq'}}
            records = [r for r in records if r.category in categories.get(topic, {topic})]
        ranked = []
        for record in records:
            def matches(word: str) -> bool:
                return bool(re.search(r'(?<!\w)' + re.escape(word.casefold()) + r'(?!\w)', normalized))
            score = sum(2 if len(word) > 3 else 1 for word in record.keywords if matches(word))
            score += sum(1 for word in re.findall(r'\w+', record.label.casefold()) if len(word) >= 3 and matches(word))
            if score:
                ranked.append((score, record))
        if ranked:
            return [r for _, r in sorted(ranked, key=lambda pair: pair[0], reverse=True)[:5]]
        return records[:5] if topic else []

    def render(self, records: list[KnowledgeRecord], language: str) -> str:
        output = []
        for record in records:
            text = record.text_ur if language == 'ur' and record.text_ur else record.text
            kb = self.knowledge
            for field in ('clinic_name', 'address', 'contact_number', 'landline', 'email'):
                text = text.replace('{' + field + '}', getattr(kb, field))
            if record.id == 'hours' and kb.opening_hours.get('status') == 'verified' and kb.opening_hours.get('value'):
                text = ('کلینک کے اوقات: ' if language == 'ur' else 'Clinic opening hours: ') + kb.opening_hours['value']
            if record.category == 'prices' and record.amount is not None:
                label = record.label_ur if language == 'ur' and record.label_ur else record.label
                text = f'{label}: PKR {record.amount:,}.'
            if record.status == 'demo':
                prefix = 'ڈیمو — فرضی قیمت، کلینک کی تصدیق شدہ فیس نہیں: ' if language == 'ur' else 'DEMO — illustrative only, not a confirmed HM fee: '
                text = prefix + text
            output.append(text)
        return '\n\n'.join(output)

    def public_info(self) -> dict:
        kb = self.knowledge
        return {
            'clinic_name': kb.clinic_name, 'address': kb.address,
            'contact_number': kb.contact_number, 'landline': kb.landline, 'email': kb.email,
            'opening_hours': kb.opening_hours, 'reviewed_on': kb.reviewed_on,
            'demo_data_enabled': self.demo_data_enabled,
            'records': [r.model_dump() for r in self.allowed_records()],
        }

    def model_context(self, records: list[KnowledgeRecord], prior_ids: list[str]) -> dict:
        """Only curated public records and opaque topic IDs ever reach a provider."""
        return {
            'task': 'Select relevant approved public clinic records. Return JSON only: {"record_ids":["id"]}. Never write new facts. Select at least one provided ID.',
            'allowed_records': [{'id': r.id, 'label': r.label, 'text': self.render([r], 'en'), 'status': r.status} for r in records],
            'prior_topic_ids': [i for i in prior_ids if any(r.id == i for r in self.allowed_records())][-8:],
        }
