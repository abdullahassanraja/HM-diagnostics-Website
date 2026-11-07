# HM Diagnostics AI Virtual Receptionist

A separate FastAPI backend and embeddable vanilla-JavaScript chat widget for the existing HM website. No website pages, styles or routing are replaced.

See [the file map](docs/file-map.md) for a summary of the created modules.

**Ready for a local demo without credentials:** approved clinic information, clearly labelled sample prices, English/Urdu responses and a complete consent → booking details → review → Pending flow. Demo requests use fictional details and temporary memory only. No live booking is claimed.

## Quick start

From the repository root on Windows PowerShell:

```powershell
cd hm-diagnostics-chatbot
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Open **http://127.0.0.1:8000/demo** and click **Ask HM**. Health: **http://127.0.0.1:8000/health**.

On macOS/Linux, use `python3 -m venv .venv`, `.venv/bin/python`, and `cp .env.example .env` instead. No AI key is necessary for the deterministic demonstration.

Try: “CBC price”, “Where are you located?”, “Do you offer MRI?”, “How do I get my report?”, then Book an Appointment. Use a fictional name and Pakistani mobile number, a future date and a preferred time. No request is saved before consent and the final Submit request click.

## Architecture

```text
Website → widget/chatbot.js → FastAPI
                              ├─ Curated JSON lookup + approved responses
                              ├─ Gemini → Groq selector, with circuit breakers
                              ├─ Deterministic booking state machine
                              └─ Demo memory OR Google Sheets appointment store
```

No n8n, LangChain, embeddings, vector database or fine-tuning is used.

The LLM integrations are deliberately constrained: the backend sends **only curated public knowledge records and prior public topic IDs**, never the visitor’s raw message or appointment fields. Providers select approved record IDs. The backend validates those IDs and renders the corresponding approved facts itself. Provider-generated fees, preparation instructions, diagnoses and other free-form claims are not displayed. With both providers unavailable, the assistant still shares available knowledge and reception contact information.

## Update the knowledge JSON

Edit **`data/clinic_info.json`**. The application validates and reloads it when its modification time changes. No retraining or embedding refresh is required. A hosted deployment normally updates this file through Git and a redeploy; edits inside a running Render instance do not persist.

Top-level contact fields are the source of truth for `{address}`, `{contact_number}`, `{landline}`, and `{email}` placeholders in record text. To approve opening hours, set `opening_hours.status` to `verified` and supply `opening_hours.value`. Keep it unverified until the clinic confirms the schedule.

Each record has a unique `id`, `category`, `status`, `label`, `text`, `keywords`, and optional Urdu text, source URL and price amount. Status meanings:

- `verified`: a fact published in the cited clinic source. This is not independent confirmation of current availability.
- `demo`: illustrative sample data, always labelled **DEMO — not a confirmed HM fee** in replies. Hidden when `DEMO_DATA_ENABLED=false`.
- `unverified`: excluded from answers and provider context.

For prices, **`amount` is the single source of truth**, in PKR. The application formats the amount; it does not parse a price from prose. To replace a sample price after clinic approval:

```json
{
  "id": "demo-cbc",
  "category": "prices",
  "status": "verified",
  "label": "Complete blood count (CBC)",
  "label_ur": "",
  "text": "Clinic-approved fee. Confirm before visiting.",
  "text_ur": "",
  "keywords": ["cbc", "complete blood"],
  "source_url": "https://hmdiagnosticsandclinics.com/",
  "amount": 900,
  "currency": "PKR"
}
```

**The 900 above is a formatting example, not a real HM price.** Replace it with a clinic-approved value and an appropriate source. Update `reviewed_on` and `review_note`. Opening hours remain unconfirmed; do not infer them from the availability of online reporting. Medical preparation instructions should be supplied and approved by the clinic, never invented for a demo.

Validate after editing:

```powershell
.venv/Scripts/python.exe -c "from app.config import Settings; from app.services.clinic_service import ClinicService; s=Settings(); print(len(ClinicService(s.knowledge_path,s.demo_data_enabled).allowed_records()))"
```

### Refresh public source observations

```powershell
.venv/Scripts/python.exe scripts/scrape_clinic.py
```

This fetches four original HM pages and writes `data/source_review.json`, containing retrieval status, public contact matches, service mentions and content hashes. It does **not** overwrite your curated file or approve scraped prices, hours or policies. Review observations before manually updating the knowledge JSON.

## Configure Gemini and Groq

Set keys only in the backend `.env` or Render environment. Never put them in the widget or commit `.env`.

1. Set `GEMINI_API_KEY` and/or `GROQ_API_KEY`.
2. Run `.venv/Scripts/python.exe scripts/list_models.py` to list model IDs currently available to your account.
3. Set `GEMINI_MODEL` and `GROQ_MODEL` to supported text models. Choose a Gemini model supporting `generateContent` and JSON output, and a Groq chat model supporting JSON-object output. IDs are intentionally configuration, not hardcoded defaults that can become deprecated.
4. `GEMINI_ENABLED=false` by default. Before enabling, review [Gemini’s current terms](https://ai.google.dev/gemini-api/terms), including audience/region restrictions and free-tier data handling. Set it to `true` only for an eligible deployment.
5. Groq is enabled when its key and model are configured. Review [Groq’s data controls](https://console.groq.com/docs/your-data) and enable zero-data-retention settings where appropriate.

When enabled and configured, **Gemini is primary and Groq secondary**. Transient timeouts, quota errors, outages and invalid structured outputs trigger fallback. Retries are bounded; quota errors immediately switch provider while the exhausted provider cools down. Authentication/configuration failures are not repeatedly retried. Only provider name, latency, success and error category are logged. No raw provider error is shown to visitors.

Live-provider validation still requires your keys. The automated suite uses mocked APIs, including Gemini success, timeout and quota failures, Groq fallback and both providers unavailable. You can temporarily set an invalid Gemini model in a private staging environment to verify Groq fallback, then restore it. Do not deliberately exhaust quotas or rotate keys to circumvent account limits.

## Google Sheets setup

Demo mode uses memory and does not need a Google account. For live requests:

1. Create a Google Cloud project and enable the Google Sheets API.
2. Create a service account. Generate a JSON credential and keep it outside Git.
3. Create a **private** spreadsheet. Create a worksheet named `Appointments`.
4. Share the spreadsheet as Editor with the service account’s `client_email`. Give only authorized clinic staff access; do not enable “Anyone with the link”.
5. Put these exact headers in row 1, columns A through J:

```text
Request ID | Created At | Patient Name | Phone Number | Test / Service | Preferred Date | Preferred Time | Notes | Status | Source
```

6. Set `GOOGLE_SHEET_ID` from the spreadsheet URL and `GOOGLE_SHEET_NAME=Appointments`.
7. Set `GOOGLE_SERVICE_ACCOUNT_JSON` to the credential JSON as an environment secret. In `.env`, enclose the entire one-line JSON in single quotes; preserve escaped `\n` sequences in `private_key`. On Render paste valid JSON into the environment-value field; do not add shell quotes there.
8. Set `DEMO_MODE=false` and `APPOINTMENT_STORAGE=google_sheets` together. Demo mode intentionally cannot write to the clinic spreadsheet. Use fictional details for initial testing even in live-storage mode.
9. Choose whether to keep clearly labelled sample prices visible. For public clinic use, set `DEMO_DATA_ENABLED=false` until prices have been approved and changed to `verified`.
10. Set the clinic’s spreadsheet retention/access policy before collecting real requests.

The application validates phone/date/time, checks the consent and confirmation token, assigns a unique request ID, and appends **Pending** with **Website Chatbot** as the source. Times are in `Asia/Karachi`. RAW cell input and formula-prefix escaping are used.

Submissions are serialized in a **single worker**. Repeated requests use the same ID; the service checks column A before appending. An ambiguous Sheets error is not blindly retried; the next visitor retry checks the ID first. If storage fails or success cannot be verified, the API returns an error and **does not claim the request was saved**. The application does not provide database-grade exactly-once guarantees across independent service instances; do not scale it to multiple workers/replicas without shared transactional idempotency storage.

## Deploy on Render Free

The existing website can stay on Vercel. Deploy this backend as a separate Render Web Service.

1. Push this repository to GitHub.
2. In Render, choose **New → Web Service**, connect the repository, select the intended branch.
3. Set **Root Directory** to `hm-diagnostics-chatbot`, **Runtime** to Python and **Instance Type** to Free.
4. **Build Command:** `pip install -r requirements.txt`
5. **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1 --no-access-log`
6. Add environment settings from `.env.example`. For the initial demo: `ENVIRONMENT=production`, `DEMO_MODE=true`, `DEMO_DATA_ENABLED=true`, `APPOINTMENT_STORAGE=memory`, `KEEP_ALIVE_ENABLED=false`.
7. Set `ALLOWED_ORIGINS` to the exact website origins, comma-separated, without paths or trailing slashes. Include your actual Vercel origin and custom domain if used. Example shape: `https://your-site.vercel.app,https://hmdiagnosticsandclinics.com`.
8. Deploy. Render’s `RENDER_EXTERNAL_URL` is automatically allowed for the backend’s own `/demo` page. Set `PUBLIC_BASE_URL` to your actual HTTPS Render URL for optional self-pings.
9. Check `https://YOUR-RENDER-APP.onrender.com/health`; it should return `{"status":"ok"}` without calling AI or Sheets.
10. Try `/demo`. Add API keys/models and verify Gemini/Groq using the steps above. Configure Google Sheets separately before disabling demo mode.
11. Add the widget snippet to the website using the real backend URL.
12. Optionally configure one external health scheduler as described below.

`render.yaml` provides equivalent service settings for a Blueprint import using `hm-diagnostics-chatbot/render.yaml` as the Blueprint path. Manual Web Service creation above does not require Blueprint support.

Render Free has cold starts, ephemeral storage, finite hours and possible suspension; it is a demo/MVP platform, **not a 24/7 availability guarantee**. [Render Free limits](https://render.com/docs/free).

## Embed in the existing website

Add this deferred script in the shared header or before `</body>`, replacing the placeholder URL:

```html
<script defer
  src="https://YOUR-RENDER-APP.onrender.com/widget/chatbot.js"
  data-api-url="https://YOUR-RENDER-APP.onrender.com"></script>
```

Add it once per page or in your site’s shared template. The script has a duplicate-widget guard. Its Shadow DOM keeps widget styles separate from the website. It does not modify website navigation or forms. Do not put a secret in `data-api-url`.

For this repository, the five HTML files are `dist/index.html`, `dist/about/index.html`, `dist/services/index.html`, `dist/doctors/index.html`, and `dist/contact/index.html`. **No live snippet has been inserted yet**, because the real backend URL is not configured.

If your site uses a Content Security Policy, allow the exact backend origin for `script-src`, `style-src` (the widget stylesheet), and `connect-src`. Do not broadly allow arbitrary third-party origins.

## Health checks every 12 minutes

`GET /health` is lightweight and never invokes AI or Sheets. Pick **one** external scheduler if periodic checks are needed.

### Preferred external option: cron-job.org

Create a free HTTP job with URL `https://YOUR-RENDER-APP.onrender.com/health`, method GET and a 12-minute interval (custom cron: `*/12 * * * *`). Allow enough timeout for a cold start where supported. Enable the job yourself after the backend is deployed. No scheduler is configured automatically by this repository.

### Optional GitHub Actions

The repository contains `.github/workflows/receptionist-health.yml`. It is disabled until the repository variable `RECEPTIONIST_HEALTH_CHECK_ENABLED` equals `true`. Set `RECEPTIONIST_HEALTH_URL` to the HTTPS `/health` URL. It supports manual execution and a 12-minute cron schedule. GitHub schedules can be delayed or skipped and can be disabled after inactivity; they do not provide exact timing. Do not enable it if cron-job.org is already checking the service.

### Optional internal self-ping

Set `KEEP_ALIVE_ENABLED=true`, `KEEP_ALIVE_INTERVAL_SECONDS=720`, and `PUBLIC_BASE_URL` to the backend HTTPS origin. The asynchronous task starts once per worker during lifespan startup, applies a timeout, logs status/latency and cancels cleanly at shutdown. It is disabled by default and in tests. **A suspended service cannot run its own loop**, so this is not a reliable replacement for an external check. No second paid service is needed. Neither option guarantees uptime or overrides hosting limits.

## Environment reference

| Variables | Purpose |
| --- | --- |
| `DEMO_MODE`, `DEMO_DATA_ENABLED` | Fictional-request mode and visibility of sample knowledge |
| `APPOINTMENT_STORAGE` | `memory` for demo or `google_sheets` for live requests |
| `GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_ENABLED` | Primary provider, only when configured and eligible |
| `GROQ_API_KEY`, `GROQ_MODEL`, `GROQ_ENABLED` | Secondary provider |
| `GOOGLE_SHEET_ID`, `GOOGLE_SHEET_NAME`, `GOOGLE_SERVICE_ACCOUNT_JSON` | Private appointment destination |
| `ALLOWED_ORIGINS`, `PUBLIC_BASE_URL` | Exact permitted website origins and backend URL |
| `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES`, `LLM_CIRCUIT_FAILURES`, `LLM_CIRCUIT_SECONDS` | Provider timeout, retries and cooldown |
| `SESSION_TTL_MINUTES`, `MAX_SESSIONS` | Expiration and maximum in-memory sessions |
| `DEMO_RETENTION_MINUTES` | Demo-request expiration; background cleanup every 30 seconds |
| `RATE_LIMIT_ENABLED`, `RATE_LIMIT_PER_MINUTE`, `MAX_REQUEST_BYTES` | Basic request abuse protection |
| `KEEP_ALIVE_ENABLED`, `KEEP_ALIVE_INTERVAL_SECONDS` | Optional self-health-check task |
| `TIMEZONE`, `KNOWLEDGE_FILE` | Timezone and curated JSON location |

## API

- `GET /health`: `{"status":"ok"}` only.
- `GET /api/config`: public widget configuration, no credentials.
- `GET /api/clinic-info`: allowed public records, including demo tags when enabled.
- `POST /api/chat`: `{message, session_id?, action?, consent?, language?}` → reply, state, actions, and review data when appropriate.
- `POST /api/appointments`: `{session_id, confirmation_token, idempotency_key, confirmed:true}` → verified saved status, Pending and demo/live indication.

Sessions are bearer-style random tokens in JSON request bodies, kept only in widget memory. Unknown/expired sessions receive 401. `/docs` is available locally; disabled in production.

## Privacy and MVP limitations

- Appointment PII is processed by the deterministic state machine and storage adapter, not the LLM router. No raw conversation is sent to either provider.
- Explicit consent is required before collecting contact details, and explicit confirmation before saving.
- No CNIC, payment information, reports, diagnoses or medical history are requested. Scheduling notes are optional and guarded against common sensitive inputs.
- Input validation, body-size caps, exact CORS origins, bounded sessions, basic IP rate limiting and constant-time confirmation checks are included.
- No browser localStorage or sessionStorage is used. The widget clears sensitive booking display after submission/cancel and clears chats after inactivity. Browser timers are best-effort; server expiration is authoritative.
- Memory sessions and demo requests disappear on restart and are not suitable for durable cross-restart sessions. Expired data is cleaned periodically and on access. Use an external persistent, access-controlled session/idempotency store before scaling or requiring continuity.
- Retention for live Sheets records must be implemented and governed by clinic staff. The app does not silently delete clinic records. Configure a retention policy before going live.
- No appointment data is written to local files. Keep reverse-proxy/request-body logging disabled. The provided start command disables Uvicorn access logs; logs contain only generic operational/provider metadata.
- CORS is not authentication. This is a public receptionist with basic abuse protection, not a clinical record system, an authenticated patient portal, or a compliance certification. Rate limiting is per-process and does not trust spoofable forwarded IP headers.
- Prefer HTTPS outside localhost. Do not expose the development server to the public internet.

## Tests

```powershell
.venv/Scripts/python.exe -m pytest -q
node --check widget/chatbot.js
```

Optional widget DOM interaction tests (Node.js is needed only for these development checks):

```sh
cd widget
npm ci
npm test
```

`constraints.txt` records the Python package versions used for validation. Runtime installation does not install development-only packages merely because they appear as constraints. Update the constraints deliberately when upgrading dependencies.

External AI and Google APIs are mocked. Tests cover primary-provider success, transient failures and fallback, unusable output, circuits/retries, both providers unavailable, consent, phone/date/time validation, final confirmation, idempotency, Sheets errors and RAW writes, knowledge restrictions, PII isolation, expiry, CORS/rate/body limits, health and keep-alive start/cancellation.

**Not verified without your credentials:** real model access/quota behavior, service-account permissions, actual Sheets writes, Render deployment, cross-origin live embedding and external scheduler execution.

## Troubleshooting

- **Chat cannot connect:** confirm the backend URL and HTTPS, check `/health`, then exact `ALLOWED_ORIGINS`. A Render cold start may require retrying after a minute.
- **No AI provider shown:** the key/model is missing, the provider is disabled, or its circuit is cooling down. The public-knowledge demo still works.
- **Gemini skipped:** check `GEMINI_ENABLED`, eligibility, current model ID and credentials. Never paste keys into chat or frontend code.
- **Request not saved:** check the Sheet ID, service-account share, exact worksheet/header names, and `APPOINTMENT_STORAGE`. Retry the same review request; do not repeatedly start fresh requests after an ambiguous storage error.
- **Chat expired:** start again. This does not resubmit a previous booking.
- **Changed knowledge not showing:** validate JSON/schema and demo flags; deploy the changed file to Render. Sample prices disappear when demo data is disabled.

## Remaining manual setup

Deploy the backend, supply API keys/model IDs, approve real knowledge, configure the private Google Sheet and retention policy, set website origins, insert the real widget URL, test the live integrations, and optionally enable exactly one health scheduler. The existing website remains untouched until you add the embed snippet.
