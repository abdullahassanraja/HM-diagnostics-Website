"""List current model IDs using configured keys, without exposing the keys."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from app.config import Settings


async def main():
    settings = Settings()
    async with httpx.AsyncClient(timeout=15) as client:
        if settings.gemini_api_key.get_secret_value():
            response = await client.get('https://generativelanguage.googleapis.com/v1beta/models', headers={'x-goog-api-key': settings.gemini_api_key.get_secret_value()})
            if response.is_success:
                print('Gemini generateContent model IDs:')
                for model in response.json().get('models', []):
                    if 'generateContent' in model.get('supportedGenerationMethods', []): print(model['name'].removeprefix('models/'))
            else: print('Gemini model listing failed:', response.status_code)
        if settings.groq_api_key.get_secret_value():
            response = await client.get('https://api.groq.com/openai/v1/models', headers={'Authorization': 'Bearer ' + settings.groq_api_key.get_secret_value()})
            if response.is_success:
                print('Groq model IDs:')
                for model in response.json().get('data', []): print(model['id'])
            else: print('Groq model listing failed:', response.status_code)
        if not settings.gemini_api_key.get_secret_value() and not settings.groq_api_key.get_secret_value():
            print('Set API keys in the server-side .env first. Never put them in the widget.')


if __name__ == '__main__': asyncio.run(main())
