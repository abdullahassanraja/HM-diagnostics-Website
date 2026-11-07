from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / '.env', extra='ignore')
    app_name: str = 'HM Diagnostics AI Receptionist'
    environment: str = 'development'
    demo_mode: bool = True
    demo_data_enabled: bool = True
    appointment_storage: Literal['memory', 'google_sheets'] = 'memory'
    gemini_api_key: SecretStr = SecretStr('')
    gemini_model: str = ''
    gemini_enabled: bool = False
    groq_api_key: SecretStr = SecretStr('')
    groq_model: str = ''
    groq_enabled: bool = True
    llm_timeout_seconds: float = Field(8, ge=0.1, le=30)
    llm_max_retries: int = Field(1, ge=0, le=2)
    llm_circuit_failures: int = Field(2, ge=1, le=10)
    llm_circuit_seconds: int = Field(60, ge=1, le=3600)
    google_sheet_id: str = ''
    google_sheet_name: str = 'Appointments'
    google_service_account_json: SecretStr = SecretStr('')
    allowed_origins: str = 'http://127.0.0.1:8000,http://localhost:8000,http://127.0.0.1:4173,http://localhost:4173'
    public_base_url: str = ''
    render_external_url: str = ''
    keep_alive_enabled: bool = False
    keep_alive_interval_seconds: int = Field(720, ge=60)
    session_ttl_minutes: int = Field(30, ge=1, le=120)
    max_sessions: int = Field(1000, ge=1, le=10000)
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = Field(30, ge=1, le=300)
    max_request_bytes: int = Field(8192, ge=512, le=32768)
    timezone: str = 'Asia/Karachi'
    knowledge_file: str = 'data/clinic_info.json'
    demo_retention_minutes: int = Field(30, ge=1, le=120)

    @property
    def origins(self) -> list[str]:
        values = [value.strip().rstrip('/') for value in self.allowed_origins.split(',') if value.strip()]
        return list(dict.fromkeys(values + [v.rstrip('/') for v in (self.public_base_url, self.render_external_url) if v]))

    @property
    def knowledge_path(self) -> Path:
        file = Path(self.knowledge_file)
        return file if file.is_absolute() else BASE_DIR / file

    @model_validator(mode='after')
    def deployment_checks(self) -> 'Settings':
        ZoneInfo(self.timezone)
        if self.appointment_storage == 'memory' and not self.demo_mode:
            raise ValueError('Memory appointment storage is available only in demo mode.')
        if self.demo_mode and self.appointment_storage != 'memory':
            raise ValueError('Demo requests must use memory storage. Disable DEMO_MODE before enabling clinic Google Sheets.')
        if '*' in self.origins:
            raise ValueError('Configure explicit origins, not wildcard CORS.')
        if self.environment == 'production' and not self.origins:
            raise ValueError('Production requires configured allowed origins.')
        return self
