from urllib.parse import quote

import httpx

from app.config import Settings
from app.services.provider_base import ProviderError, check_response, serialize_context


class GeminiService:
    name = 'gemini'

    def __init__(self, settings: Settings, client: httpx.AsyncClient):
        self.settings, self.client = settings, client
        self.available = bool(settings.gemini_enabled and settings.gemini_model and settings.gemini_api_key.get_secret_value())

    async def generate(self, context: dict) -> str:
        model = quote(self.settings.gemini_model.removeprefix('models/'), safe='')
        try:
            response = await self.client.post(
                f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
                headers={'x-goog-api-key': self.settings.gemini_api_key.get_secret_value()},
                json={'contents': [{'role': 'user', 'parts': [{'text': serialize_context(context)}]}],
                      'generationConfig': {'temperature': 0, 'maxOutputTokens': 300, 'responseMimeType': 'application/json'}},
                timeout=self.settings.llm_timeout_seconds,
            )
            check_response(response)
            parts = response.json()['candidates'][0]['content']['parts']
            text = ''.join(part.get('text', '') for part in parts)
            if not text.strip(): raise ProviderError('invalid_response')
            return text
        except httpx.TimeoutException as error:
            raise ProviderError('timeout') from None
        except httpx.RequestError:
            raise ProviderError('unavailable') from None
        except (ValueError, KeyError, IndexError, TypeError):
            raise ProviderError('invalid_response') from None
