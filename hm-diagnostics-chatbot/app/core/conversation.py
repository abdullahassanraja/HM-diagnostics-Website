"""Booking state is deterministic and entirely separate from provider context."""
import re
import secrets
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.config import Settings
from app.core.security import URGENT_PATTERN, scheduling_notes, sensitive_text
from app.core.session_manager import Session
from app.models.schemas import ChatInput, ChatOutput, QuickAction, normalize_phone
from app.services.clinic_service import ClinicService
from app.services.llm_router import LLMRouter

WELCOME = "Assalam-o-Alaikum! 👋 Welcome to HM Diagnostics Islamabad. I'm your virtual receptionist, and I'm happy to help. Are you looking for a test, a specialist, or help planning a visit?"
WELCOME_UR = 'السلام علیکم! 👋 HM Diagnostics اسلام آباد میں خوش آمدید۔ میں آپ کا ورچوئل استقبالیہ معاون ہوں، خوشی سے مدد کروں گا۔ کیا آپ کسی ٹیسٹ، ڈاکٹر یا وزٹ کے بارے میں جاننا چاہتے ہیں؟'
ACTIONS = [('Book an Appointment', 'book'), ('Ask About Tests', 'tests'), ('Test Prices', 'prices'), ('Opening Hours & Location', 'hours'), ('Talk to Reception', 'reception')]
ACTIONS_UR = [('اپائنٹمنٹ کی درخواست', 'book'), ('ٹیسٹ کے بارے میں پوچھیں', 'tests'), ('ٹیسٹ کی قیمتیں', 'prices'), ('اوقات اور پتہ', 'hours'), ('استقبالیہ سے بات کریں', 'reception')]


class Conversation:
    def __init__(self, settings: Settings, clinic: ClinicService, router: LLMRouter):
        self.settings, self.clinic, self.router = settings, clinic, router

    def say(self, session: Session, en: str, ur: str) -> str:
        return ur if session.language == 'ur' else en

    def output(self, session: Session, text: str, actions=None, **extra) -> ChatOutput:
        if actions is None: actions = ACTIONS_UR if session.language == 'ur' else ACTIONS
        return ChatOutput(session_id=session.id, reply=text, state=session.stage, demo_mode=self.settings.demo_mode,
                          language=session.language, quick_actions=[QuickAction(label=l, action=a) for l, a in actions], **extra)

    def contact(self, session: Session) -> str:
        kb = self.clinic.knowledge
        return self.say(session, f'Our reception team can help you with the details. You can reach them on {kb.contact_number} or {kb.landline}.', f'ہمارا استقبالیہ عملہ تفصیلات میں مدد کر سکتا ہے۔ {kb.contact_number} یا {kb.landline} پر رابطہ کریں۔')

    def validate_date(self, value: str) -> str:
        try: parsed = date.fromisoformat(value.strip())
        except ValueError: raise ValueError('Please use YYYY-MM-DD, for example 2026-12-15.') from None
        today = datetime.now(ZoneInfo(self.settings.timezone)).date()
        if parsed < today: raise ValueError('Please choose today or a future date.')
        if parsed > today + timedelta(days=365): raise ValueError('Please choose a date within the next year.')
        return parsed.isoformat()

    async def respond(self, session: Session, payload: ChatInput) -> ChatOutput:
        session.language = payload.language
        text, action = payload.message.strip(), payload.action
        if URGENT_PATTERN.search(text):
            session.reset()
            return self.output(session, self.say(session,
                'This may need urgent medical attention. Please contact local emergency services or go to the nearest emergency department now. Do not wait for this chat or an appointment request.',
                'یہ فوری طبی مدد کا معاملہ ہو سکتا ہے۔ فوراً مقامی ایمرجنسی سروس یا قریبی ایمرجنسی شعبے سے رابطہ کریں۔ اس چیٹ یا اپائنٹمنٹ کا انتظار نہ کریں۔'), [])
        if action == 'cancel' or text.casefold() in {'cancel', 'منسوخ'}:
            session.reset()
            return self.output(session, self.say(session, 'I’ve cleared the current enquiry. How else can I help?', 'موجودہ درخواست صاف کر دی گئی ہے۔ میں مزید کیسے مدد کر سکتا ہوں؟'))
        if action == 'restart':
            session.reset()
            return self.output(session, self.say(session, WELCOME, WELCOME_UR))
        if session.stage not in {'idle', 'submitted'} and action not in {'book', 'callback'}:
            return self.collect(session, payload)
        # Close politely when a visitor is finished; do not turn a thank-you or refusal
        # into an unwanted booking. These branches never invoke an LLM or store PII.
        normalized = text.casefold().strip(' .!?،؟')
        if not action and normalized in {'bye', 'goodbye', 'allah hafiz', 'khuda hafiz', 'خدا حافظ', 'اللہ حافظ'}:
            session.next_step = ''
            return self.output(session, self.say(session, 'Thank you for visiting HM Diagnostics. Take care, and you’re welcome to return whenever you need help. Allah Hafiz!', 'HM Diagnostics سے رابطہ کرنے کا شکریہ۔ اپنا خیال رکھیے، جب بھی مدد چاہیے ہم حاضر ہیں۔ اللہ حافظ!'), [])
        if not action and (normalized in {'no', 'no thanks', 'not now', 'just looking', 'just browsing', 'later', 'نہیں', 'ابھی نہیں', 'بعد میں'} or re.match(r"^(?:no[ ,]+thanks|not now|just browsing|i(?:'m| am) not (?:ready|interested))\b", normalized)):
            session.next_step = ''
            return self.output(session, self.say(session, 'Of course—take your time. You’re welcome to ask another question whenever you’re ready. Our reception team is here if you need a hand.', 'بالکل، آپ اطمینان سے فیصلہ کریں۔ جب چاہیں مزید سوال پوچھ سکتے ہیں، ہمارا استقبالیہ عملہ مدد کے لیے حاضر ہے۔'), [('Ask About Tests', 'tests'), ('Talk to Reception', 'reception')])
        if not action and normalized in {'thanks', 'thank you', 'thankyou', 'shukriya', 'شکریہ', 'بہت شکریہ'}:
            session.next_step = ''
            return self.output(session, self.say(session, 'You’re very welcome! Is there anything else you’d like to know? I’m happy to help with a test enquiry or planning your visit whenever you’re ready.', 'بہت خوشی ہوئی! کیا آپ کچھ اور جاننا چاہیں گے؟ جب آپ چاہیں ٹیسٹ کی معلومات یا وزٹ کی درخواست میں مدد کر سکتا ہوں۔'), [('Ask another test question', 'tests'), ('Talk to Reception', 'reception')])
        if not action and normalized in {'yes', 'yes please', 'sure', 'please do', 'go ahead', 'جی', 'جی ہاں', 'ہاں'}:
            if session.next_step:
                action = session.next_step
            else:
                return self.output(session, self.say(session, 'Of course—what would you like help with: a test, finding a specialist, or planning a visit?', 'ضرور، آپ کس بارے میں مدد چاہتے ہیں: ٹیسٹ، ڈاکٹر کی تلاش، یا وزٹ کی درخواست؟'))
        if action in {'book', 'callback'} or re.search(r'\b(book|appointment|callback)\b|اپائنٹمنٹ|بکنگ', text, re.I):
            interest = session.interest_service
            session.reset(); session.stage = 'consent'
            session.interest_service = interest
            session.fields['kind'] = 'Callback request' if action == 'callback' else 'Appointment request'
            notice = self.say(session,
                'Of course—I can help you prepare a request, one step at a time. May I collect your name, Pakistani mobile number, service, and preferred date/time? Booking details stay out of AI calls. Please share scheduling details only, not reports or medical history. You can cancel before submission.',
                'ضرور، میں مرحلہ وار درخواست تیار کرنے میں مدد کروں گا۔ کیا میں آپ کا نام، پاکستانی موبائل نمبر، سروس اور پسندیدہ تاریخ و وقت لے سکتا ہوں؟ یہ تفصیلات AI کو نہیں بھیجی جاتیں۔ صرف شیڈول کی معلومات دیں، میڈیکل رپورٹس نہیں۔ جمع کرانے سے پہلے منسوخ کر سکتے ہیں۔')
            if self.settings.demo_mode:
                notice += self.say(session, f'\n\nDEMO ONLY: use fictional details. Demo requests are kept in memory for up to {self.settings.demo_retention_minutes} minutes and are not sent to the clinic.', '\n\nصرف ڈیمو: فرضی معلومات استعمال کریں۔ یہ درخواست کلینک کو نہیں بھیجی جائے گی۔')
            else:
                notice += self.say(session, '\n\nConfirmed requests are stored in a Google Sheet accessible to authorized clinic staff, subject to the clinic’s retention policy.', '\n\nتصدیق کے بعد درخواست کلینک کے مجاز عملے کی گوگل شیٹ میں محفوظ ہو گی۔')
            return self.output(session, notice, [('I consent / میں متفق ہوں', 'consent'), ('Cancel', 'cancel')])
        if (not text and not action) or text.casefold() in {'hi', 'hello', 'aoa', 'assalam o alaikum', 'assalam-o-alaikum', 'سلام', 'السلام علیکم'}:
            return self.output(session, self.say(session, WELCOME, WELCOME_UR) + (self.say(session, '\n\nDemo: sample prices are illustrative; use fictional booking details.', '\n\nڈیمو: قیمتیں فرضی ہیں، بکنگ کے لیے فرضی معلومات دیں۔') if self.settings.demo_mode else ''))
        if action == 'reception':
            session.next_step = 'callback'
            return self.output(session, self.contact(session) + self.say(session, '\n\nWould you like help preparing a callback request?', '\n\nکیا آپ رابطے کی درخواست تیار کروانا چاہیں گے؟'), [('Request a callback', 'callback'), ('Book an Appointment', 'book')])
        if sensitive_text(text):
            session.next_step = ''
            return self.output(session, self.say(session, 'I understand you’d like some guidance. Please discuss symptoms or medical reports with a qualified clinician; I can help connect you with reception for clinic arrangements. ', 'میں سمجھتا ہوں کہ آپ رہنمائی چاہتے ہیں۔ علامات یا میڈیکل رپورٹس کے لیے ڈاکٹر سے مشورہ کریں؛ کلینک سے رابطے میں مدد کے لیے استقبالیہ موجود ہے۔ ') + self.contact(session), [('Talk to Reception', 'reception')])
        topic = action if action in {'tests', 'prices', 'hours', 'doctors', 'preparation'} else None
        if re.search(r'price|cost|fee|charges|قیمت|فیس', text, re.I): topic = 'prices'
        if re.search(r'fasting|prepar|خالی پیٹ|تیاری', text, re.I): topic = 'preparation'
        if re.search(r'doctors?|specialist|ڈاکٹر', text, re.I) and topic is None: topic = 'doctors'
        if re.search(r'hours|opening|timing|اوقات', text, re.I) and topic is None: topic = 'hours'
        if re.search(r'\b(?:services|tests|departments)\b|خدمات', text, re.I) and topic is None: topic = 'tests'
        records = self.clinic.find(text, topic)
        if topic == 'prices' and action != 'prices':
            price_records = [r for r in self.clinic.allowed_records() if r.category == 'prices']
            generic_price_question = re.fullmatch(r'(?:please |what are (?:your |the )?)?(?:test )?(?:prices?|costs?|fees?|price list)[?.! ]*', text.casefold())
            matched_test = any(word.casefold() in text.casefold() for r in price_records for word in r.keywords if word != 'price list')
            if generic_price_question:
                previous = [r for r in price_records if r.id in session.topics]
                records = previous or price_records[:5]
            elif not matched_test:
                records = []
        if action == 'hours': records = [r for r in self.clinic.allowed_records() if r.id in {'hours', 'location', 'reception'}]
        if not records:
            session.next_step = 'callback'
            return self.output(session, self.say(session, 'I don’t have a confirmed answer for that just yet. ', 'اس بارے میں ابھی میرے پاس تصدیق شدہ جواب نہیں۔ ') + self.contact(session) + self.say(session, '\n\nWould you like me to help prepare a callback request?', '\n\nکیا میں آپ کے لیے رابطے کی درخواست تیار کروں؟'), [('Request a callback', 'callback'), ('Talk to Reception', 'reception')])
        context = self.clinic.model_context(records, session.topics)
        selected, provider = await self.router.select(context)
        # Both integrations are selection-only: model-written facts are never displayed.
        if selected: records = [r for r in records if r.id in selected]
        session.topics = (session.topics + [r.id for r in records])[-8:]
        answer = self.clinic.render(records, session.language)
        categories = {r.category for r in records}
        session.interest_service = records[0].label if len(records) == 1 and categories & {'services', 'tests', 'prices', 'doctors'} else ''
        if 'prices' in categories:
            session.next_step = 'callback'
            intro = self.say(session, 'Happy to help—here’s the pricing information currently available.\n\n', 'ضرور، اس وقت دستیاب قیمت کی معلومات یہ ہیں:\n\n')
            followup = self.say(session, '\n\nWould you like reception to confirm the current fee and availability? I can help prepare a callback request.', '\n\nکیا آپ استقبالیہ سے موجودہ فیس اور دستیابی کی تصدیق چاہیں گے؟ میں رابطے کی درخواست تیار کر سکتا ہوں۔')
            actions = [('Check fee with reception', 'callback'), ('Plan a visit', 'book')]
        elif categories & {'services', 'tests', 'doctors'}:
            session.next_step = 'book'
            intro = self.say(session, 'Of course—here’s what I can share.\n\n', 'ضرور، دستیاب معلومات یہ ہیں:\n\n')
            followup = self.say(session, '\n\nWould you like help requesting a visit, or would you prefer to speak with reception first?', '\n\nکیا آپ وزٹ کی درخواست تیار کروانا چاہیں گے یا پہلے استقبالیہ سے بات کرنا پسند کریں گے؟')
            actions = [('Request a visit', 'book'), ('Talk to Reception', 'reception')]
        else:
            session.next_step = 'callback'
            intro = self.say(session, 'I’m happy to help.\n\n', 'خوشی سے مدد کروں گا۔\n\n')
            followup = self.say(session, '\n\nIs there anything else you’d like to check before visiting? I can also help prepare a callback request.', '\n\nکیا آنے سے پہلے کچھ اور معلوم کرنا چاہیں گے؟ میں رابطے کی درخواست میں بھی مدد کر سکتا ہوں۔')
            actions = [('Ask About Tests', 'tests'), ('Request a callback', 'callback')]
        answer = intro + answer + followup
        if not provider and any(p.available for p in self.router.providers):
            answer = self.say(session, 'The AI connection is temporarily unavailable; here is the approved clinic information I can share.\n\n', 'AI عارضی طور پر دستیاب نہیں۔ کلینک کی دستیاب معلومات یہ ہیں:\n\n') + answer + '\n\n' + self.contact(session)
        return self.output(session, answer, actions, sources=list(dict.fromkeys(r.source_url for r in records if r.source_url)), provider=provider)

    def collect(self, session: Session, payload: ChatInput) -> ChatOutput:
        text, action = payload.message.strip(), payload.action
        cancel = [('Cancel', 'cancel')]
        if session.stage == 'consent':
            if action != 'consent' or not payload.consent:
                return self.output(session, self.say(session, 'Please choose “I consent” to continue, or cancel. No contact details have been requested yet.', 'جاری رکھنے کے لیے رضامندی دیں یا منسوخ کریں۔'), [('I consent / میں متفق ہوں', 'consent'), ('Cancel', 'cancel')])
            session.consent = True; session.stage = 'name'
            return self.output(session, self.say(session, 'Thank you. Let’s start with your full name—what name should I use for the request?', 'شکریہ۔ پہلے آپ کا مکمل نام بتا دیں، درخواست کس نام سے تیار کروں؟'), cancel)
        try:
            if session.stage == 'name':
                if not 2 <= len(text) <= 80 or not all(c.isalpha() or c in " '-’" for c in text) or sensitive_text(text): raise ValueError('Please enter a name using letters, spaces, hyphens or apostrophes only.')
                session.fields['patient_name'] = text; session.stage = 'phone'
                return self.output(session, self.say(session, 'Thank you. What Pakistani mobile number should reception use to follow up? For example: 03XXXXXXXXX.', 'شکریہ۔ استقبالیہ آپ سے کس پاکستانی موبائل نمبر پر رابطہ کرے؟ مثال: 03XXXXXXXXX۔'), cancel)
            if session.stage == 'phone':
                session.fields['phone'] = normalize_phone(text); session.stage = 'service'
                question = self.say(session, 'Which test, service, specialist, or callback topic would you like help with?', 'آپ کس ٹیسٹ، سروس، ڈاکٹر یا رابطے کی درخواست میں مدد چاہتے ہیں؟')
                actions = cancel
                if session.interest_service:
                    question += self.say(session, f' We were discussing {session.interest_service}; you can choose that below or type something else.', f' ہم {session.interest_service} کے بارے میں بات کر رہے تھے؛ نیچے وہی منتخب کریں یا دوسری سروس لکھیں۔')
                    actions = [(session.interest_service, 'use_interest'), ('Cancel', 'cancel')]
                return self.output(session, question, actions)
            if session.stage == 'service':
                if action == 'use_interest' and session.interest_service: text = session.interest_service
                if not 2 <= len(text) <= 100 or sensitive_text(text) or re.search(r'[<>\x00-\x1f]', text): raise ValueError('Please enter the service or specialist name only, without symptoms or personal details.')
                session.fields['service'] = text; session.stage = 'date'
                return self.output(session, self.say(session, 'Certainly. What date would suit you? Use YYYY-MM-DD, and reception will need to confirm availability.', 'ضرور۔ آپ کے لیے کون سی تاریخ مناسب ہے؟ YYYY-MM-DD میں لکھیں، دستیابی کی تصدیق استقبالیہ کرے گا۔'), cancel)
            if session.stage == 'date':
                session.fields['preferred_date'] = self.validate_date(text); session.stage = 'time'
                return self.output(session, self.say(session, 'What time would you prefer? Use 24-hour HH:MM, for example 14:30. This is a preference, not an available slot.', 'پسندیدہ وقت 24 گھنٹے کے HH:MM فارمیٹ میں لکھیں، مثلاً 14:30۔ یہ صرف ترجیح ہے۔'), cancel)
            if session.stage == 'time':
                try: value = datetime.strptime(text, '%H:%M').strftime('%H:%M')
                except ValueError: raise ValueError('Please use a valid 24-hour time such as 14:30.') from None
                session.fields['preferred_time'] = value; session.stage = 'notes'
                return self.output(session, self.say(session, 'Any scheduling note? This is optional—choose Skip. Please do not include medical history or reports.', 'کوئی شیڈول سے متعلق نوٹ؟ اختیاری ہے؛ Skip منتخب کر سکتے ہیں۔ طبی تفصیلات نہ لکھیں۔'), [('Skip / چھوڑ دیں', 'skip'), ('Cancel', 'cancel')])
            if session.stage == 'notes':
                session.fields['notes'] = '' if action == 'skip' or text.casefold() in {'skip', 'none', 'no', 'نہیں'} else scheduling_notes(text)
                session.stage = 'review'; session.confirmation_token = secrets.token_urlsafe(32)
            if session.stage == 'review':
                summary = {k: v for k, v in session.fields.items() if k != 'kind'}
                return self.output(session, self.say(session, 'You’re nearly there—thank you. Please check the details below and choose “Submit request” if they’re correct. Your request will remain Pending until reception confirms availability.', 'درخواست تقریباً تیار ہے، شکریہ۔ نیچے تفصیلات دیکھیں اور درست ہونے پر درخواست جمع کریں۔ استقبالیہ کی تصدیق تک حیثیت Pending رہے گی۔'), [('Start again', 'book'), ('Cancel', 'cancel')], summary=summary, confirmation_token=session.confirmation_token, idempotency_key=session.request_id)
        except ValueError as error:
            return self.output(session, str(error), cancel if session.stage != 'notes' else [('Skip / چھوڑ دیں', 'skip'), ('Cancel', 'cancel')])
        return self.output(session, self.contact(session))
