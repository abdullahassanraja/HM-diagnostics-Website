"""Extract public clinic facts for review, without overwriting curated JSON or demo prices."""
import hashlib
import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
PAGES = ['https://hmdiagnosticsandclinics.com/', 'https://hmdiagnosticsandclinics.com/experienced-doctors/', 'https://hmdiagnosticsandclinics.com/our-services/', 'https://hmdiagnosticsandclinics.com/contact-us-at-hm-diagnostics-and-clinics/']
SERVICES = ['laboratory', 'MRI', 'CT scan', 'ultrasound', 'X-ray', 'cardiology', 'dermatology', 'gynecology', 'physiotherapy', 'pharmacy', 'endoscopy', 'NCS', 'ECG', 'ETT']


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.hidden = 0; self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'): self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ('script', 'style'): self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden: self.parts.append(data)


class ClinicOnlyRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlparse(newurl).hostname not in {'hmdiagnosticsandclinics.com', 'www.hmdiagnosticsandclinics.com'}:
            raise urllib.error.URLError('External redirect not followed.')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def main():
    opener = urllib.request.build_opener(ClinicOnlyRedirect)
    results = []
    for url in PAGES:
        record = {'url': url, 'checked_at': datetime.now(timezone.utc).isoformat()}
        try:
            with opener.open(urllib.request.Request(url, headers={'User-Agent': 'HM-Receptionist-KnowledgeReview/1.0'}), timeout=15) as response:
                raw = response.read(2_000_000).decode('utf-8', errors='replace')
            parser = TextParser(); parser.feed(raw)
            text = ' '.join(' '.join(parser.parts).split())
            record.update(status='retrieved', content_sha256=hashlib.sha256(raw.encode()).hexdigest(),
                          published_phones=sorted(set(re.findall(r'(?:0334[- ]?6333044|051[- ]?2340199)', text))),
                          mentioned_services=[s for s in SERVICES if re.search(r'(?<!\w)' + re.escape(s) + r'(?!\w)', text, re.I)],
                          emails=sorted(set(re.findall(r'[A-Za-z0-9._%+-]+@h?m?diagnostics[^\s<>]*|hmdiagnosticsclinic@gmail\.com', text))))
        except (urllib.error.URLError, TimeoutError) as error:
            record.update(status='unavailable', error_category=type(error).__name__)
        results.append(record)
        print(url, record['status'])
    (ROOT / 'data' / 'source_review.json').write_text(json.dumps({'sources': results, 'note': 'Review extracted facts before editing clinic_info.json. This scraper never approves prices, hours, preparation or doctor availability.'}, indent=2), encoding='utf-8')


if __name__ == '__main__': main()
