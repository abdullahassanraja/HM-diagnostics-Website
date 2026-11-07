# File map

| Location | Purpose |
| --- | --- |
| `app/main.py` | Application factory, lifespan, static widget/demo, generic validation errors |
| `app/config.py` | Validated environment settings and secrets |
| `app/api/health.py` | Dependency-free `/health` |
| `app/api/chat.py` | Chat state, public config, public knowledge API |
| `app/api/appointments.py` | Explicit-confirmation submission and idempotent receipts |
| `app/models/schemas.py` | Request, response and storage schemas; mobile normalization |
| `app/core/conversation.py` | Deterministic consent/booking state machine and grounded knowledge responses |
| `app/core/session_manager.py` | Random session tokens, expiration, per-session lock |
| `app/core/security.py` | Input guards, scheduling-note checks, size/origin/rate limits |
| `app/services/clinic_service.py` | JSON validation, reload, lookup and approved fact rendering |
| `app/services/provider_base.py` | Provider protocol and categorized integration failures |
| `app/services/gemini_service.py` | Gemini REST adapter |
| `app/services/groq_service.py` | Groq REST adapter |
| `app/services/llm_router.py` | Bounded retries, failover, circuits and approved-ID validation |
| `app/services/google_sheets.py` | Google auth, private sheet append, RAW values and request-ID lookup; demo store |
| `app/services/keep_alive.py` | Optional asynchronous self-health-check task |
| `data/clinic_info.json` | Editable clinic facts, doctors, placeholders and explicitly marked sample prices |
| `data/source_review.json` | Public-source retrieval observations and hashes |
| `widget/chatbot.js`, `widget/chatbot.css` | Isolated floating widget, accessible controls, progressive booking UI |
| `widget/demo.html` | Standalone local/backend demo page |
| `widget/package.json`, `widget/package-lock.json` | Optional reproducible widget DOM-test dependencies |
| `scripts/scrape_clinic.py` | Read-only original-site fact review; never overwrites curated knowledge |
| `scripts/list_models.py` | Current account model-ID discovery without exposing keys |
| `tests/` | Mocked backend/API/provider/storage tests and widget DOM smoke test |
| `requirements.txt`, `requirements-dev.txt`, `constraints.txt` | Runtime/development dependencies and tested-version constraints |
| `.env.example` | Credential-free environment template |
| `render.yaml` | Render Free Python service configuration |
| `README.md` | Setup, knowledge updates, API, deployment, Sheets, embedding and limitations |
| `../.github/workflows/receptionist-health.yml` | Optional external scheduler, disabled until repository variables are configured |

Package `__init__.py` files contain only module descriptions. The repository-root `.gitignore` excludes `.env`, credentials, virtual environments, caches and node_modules. No live website page was changed for this backend module.
