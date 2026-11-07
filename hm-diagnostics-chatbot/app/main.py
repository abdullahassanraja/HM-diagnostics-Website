import asyncio
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import appointments, chat, health
from app.config import BASE_DIR, Settings
from app.core.conversation import Conversation
from app.core.security import SecurityMiddleware
from app.core.session_manager import SessionManager
from app.services.clinic_service import ClinicService
from app.services.gemini_service import GeminiService
from app.services.google_sheets import GoogleSheetsStore, MemoryAppointmentStore
from app.services.groq_service import GroqService
from app.services.keep_alive import KeepAlive
from app.services.llm_router import LLMRouter


def create_app(settings: Settings | None = None, *, providers=None, store=None, transport=None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logging.getLogger('httpx').setLevel(logging.WARNING)
        async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
            app.state.settings = settings
            app.state.clinic = ClinicService(settings.knowledge_path, settings.demo_data_enabled)
            app.state.sessions = SessionManager(settings.session_ttl_minutes, settings.max_sessions)
            app.state.store = store or (MemoryAppointmentStore(settings.demo_retention_minutes) if settings.appointment_storage == 'memory' else GoogleSheetsStore(settings, client))
            # Primary Gemini, secondary Groq. Disabled/unconfigured providers are skipped.
            app.state.router = LLMRouter(providers if providers is not None else [GeminiService(settings, client), GroqService(settings, client)], settings)
            app.state.conversation = Conversation(settings, app.state.clinic, app.state.router)
            app.state.keep_alive = KeepAlive(settings, client)
            app.state.keep_alive.start()
            async def purge():
                while True:
                    await asyncio.sleep(30)
                    app.state.sessions.cleanup(); app.state.store.cleanup()
            cleanup_task = asyncio.create_task(purge(), name='hm-expiry-cleanup')
            try: yield
            finally:
                cleanup_task.cancel()
                try: await cleanup_task
                except asyncio.CancelledError: pass
                await app.state.keep_alive.stop()
                app.state.sessions.sessions.clear()
                if isinstance(app.state.store, MemoryAppointmentStore): app.state.store.records.clear()

    app = FastAPI(title=settings.app_name, lifespan=lifespan, docs_url='/docs' if settings.environment != 'production' else None, redoc_url=None)
    app.add_middleware(SecurityMiddleware, settings=settings)
    app.add_middleware(CORSMiddleware, allow_origins=settings.origins, allow_credentials=False, allow_methods=['GET', 'POST'], allow_headers=['Content-Type'])
    app.include_router(health.router); app.include_router(chat.router); app.include_router(appointments.router)
    app.mount('/widget', StaticFiles(directory=BASE_DIR / 'widget'), name='widget')

    @app.get('/demo', include_in_schema=False)
    async def demo(): return FileResponse(BASE_DIR / 'widget' / 'demo.html')

    @app.get('/', include_in_schema=False)
    async def index(): return JSONResponse({'service': settings.app_name, 'demo': '/demo', 'health': '/health'})

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, error: RequestValidationError):
        # Pydantic's default response echoes input; omit it for contact-data privacy.
        return JSONResponse({'detail': 'Please check the request fields.', 'fields': [list(e['loc']) for e in error.errors()]}, 422)

    return app


app = create_app()
