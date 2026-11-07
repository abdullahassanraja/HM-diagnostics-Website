import httpx

from app.config import Settings
from app.services.provider_base import ProviderError, check_response, serialize_context


class GroqService:
    name = 'groq'

    def __init__(self, settings: Settings, client: httpx.AsyncClient):
        self.settings, self.client = settings, client
        self.available = bool(settings.groq_enabled and settings.groq_model and settings.groq_api_key.get_secret_value())

    async def generate(self, context: dict) -> str:
        try:
            response = await self.client.post('https://api.groq.com/openai/v1/chat/completions',
                headers={'Authorization': 'Bearer ' + self.settings.groq_api_key.get_secret_value()},
                json={'model': self.settings.groq_model, 'temperature': 0, 'max_tokens': 300,
                      'response_format': {'type': 'json_object'},
                      'messages': [{'role': 'system', 'content': 'Select only supplied approved public records. Return JSON with a record_ids array. No other keys or new facts.'},
                                   {'role': 'user', 'content': serialize_context(context)}]},
                timeout=self.settings.llm_timeout_seconds)
            check_response(response)
            text = response.json()['choices'][0]['message']['content']
            if not isinstance(text, str) or not text.strip(): raise ProviderError('invalid_response')
            return text
        except httpx.TimeoutException:
            raise ProviderError('timeout') from None
        except httpx.RequestError:
            raise ProviderError('unavailable') from None
        except (ValueError, KeyError, IndexError, TypeError):
            raise ProviderError('invalid_response') from None
