import asyncio
import logging
import time

import httpx

from app.config import Settings

logger = logging.getLogger('hm.healthcheck')


class KeepAlive:
    def __init__(self, settings: Settings, client: httpx.AsyncClient):
        self.settings, self.client = settings, client
        self.task: asyncio.Task | None = None

    async def ping_once(self) -> None:
        started = time.monotonic()
        try:
            response = await self.client.get(self.settings.public_base_url.rstrip('/') + '/health', timeout=5, follow_redirects=False)
            logger.info('health_ping status=%d latency_ms=%d', response.status_code, (time.monotonic() - started) * 1000)
        except httpx.HTTPError:
            logger.warning('health_ping failed latency_ms=%d', (time.monotonic() - started) * 1000)

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(self.settings.keep_alive_interval_seconds)
            await self.ping_once()

    def start(self) -> None:
        if self.settings.keep_alive_enabled and self.settings.public_base_url and (self.task is None or self.task.done()):
            self.task = asyncio.create_task(self._run(), name='hm-self-healthcheck')

    async def stop(self) -> None:
        if self.task:
            self.task.cancel()
            try: await self.task
            except asyncio.CancelledError: pass
            self.task = None
