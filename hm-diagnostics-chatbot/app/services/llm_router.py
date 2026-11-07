"""Bounded provider failover with circuit breakers and constrained outputs."""
import asyncio
import json
import logging
import time
from dataclasses import dataclass

from app.config import Settings
from app.services.provider_base import Provider, ProviderError

logger = logging.getLogger('hm.providers')


@dataclass
class Circuit:
    failures: int = 0
    open_until: float = 0


class LLMRouter:
    def __init__(self, providers: list[Provider], settings: Settings):
        self.providers, self.settings = providers, settings
        self.circuits = {provider.name: Circuit() for provider in providers}

    @staticmethod
    def validate_output(text: str, allowed_ids: set[str]) -> list[str]:
        try:
            output = json.loads(text)
            if not isinstance(output, dict) or set(output) != {'record_ids'}: raise ValueError
            ids = output['record_ids']
            if not isinstance(ids, list) or not 1 <= len(ids) <= 5: raise ValueError
            if any(not isinstance(i, str) or i not in allowed_ids for i in ids): raise ValueError
            return list(dict.fromkeys(ids))
        except (ValueError, TypeError, KeyError):
            raise ProviderError('invalid_response') from None

    async def select(self, context: dict) -> tuple[list[str] | None, str | None]:
        allowed_ids = {record['id'] for record in context['allowed_records']}
        for provider in self.providers:
            circuit = self.circuits[provider.name]
            if not provider.available or circuit.open_until > time.monotonic(): continue
            started = time.monotonic()
            failure = ProviderError('unavailable')
            for attempt in range(self.settings.llm_max_retries + 1):
                try:
                    async with asyncio.timeout(self.settings.llm_timeout_seconds):
                        response = await provider.generate(context)
                    ids = self.validate_output(response, allowed_ids)
                    circuit.failures, circuit.open_until = 0, 0
                    logger.info('provider=%s latency_ms=%d success=true', provider.name, (time.monotonic() - started) * 1000)
                    return ids, provider.name
                except (TimeoutError, asyncio.TimeoutError): failure = ProviderError('timeout')
                except ProviderError as error: failure = error
                except Exception: failure = ProviderError('unavailable')
                # Switch immediately on quota exhaustion; don't sit in a long Retry-After sleep.
                if not failure.transient or failure.category == 'rate_limit' or attempt >= self.settings.llm_max_retries: break
                await asyncio.sleep(min(1.0, 0.2 * 2 ** attempt))
            circuit.failures += 1
            if failure.category in {'authentication', 'configuration'}:
                circuit.open_until = time.monotonic() + max(300, self.settings.llm_circuit_seconds)
            elif failure.category == 'rate_limit' or circuit.failures >= self.settings.llm_circuit_failures:
                circuit.open_until = time.monotonic() + max(failure.retry_after, self.settings.llm_circuit_seconds)
            logger.warning('provider=%s latency_ms=%d success=false category=%s', provider.name, (time.monotonic() - started) * 1000, failure.category)
        return None, None
