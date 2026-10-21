"""Independent polling and honest freshness reporting for each source."""
import asyncio
from datetime import timedelta
import logging
import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util
from .parser import GOV_URL, MARKET_URL, parse_government, parse_market
from .freshness import ERROR_INTERVAL, POLL_INTERVAL, retry_after_seconds

_LOGGER = logging.getLogger(__name__)

class FuelCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry, source):
        super().__init__(hass, _LOGGER, name=f'Poland fuel prices {source}',
                         config_entry=entry, update_interval=POLL_INTERVAL)
        self.source = source
        self.url = GOV_URL if source == 'government' else MARKET_URL
        self.parser = parse_government if source == 'government' else parse_market
        self.store = Store(hass, 1, f'poland_fuel_prices.{source}')
        self.snapshot = {}

    async def _async_setup(self):
        cached = await self.store.async_load()
        if isinstance(cached, dict):
            self.snapshot = cached

    async def _async_update_data(self):
        attempted = dt_util.utcnow().isoformat()
        error = None
        retry_after = None
        for attempt in range(3):
            try:
                parsed = await self._async_fetch()
                self.snapshot = {**parsed, 'last_success': dt_util.utcnow().isoformat()}
                await self.store.async_save(self.snapshot)
                self.update_interval = POLL_INTERVAL
                return {**self.snapshot, 'last_attempt': attempted, 'ok': True,
                        'last_error': None}
            except (aiohttp.ClientError, TimeoutError, ValueError) as err:
                error = err
                if isinstance(err, aiohttp.ClientResponseError):
                    retry_after = retry_after_seconds(
                        (err.headers or {}).get('Retry-After'), dt_util.utcnow())
                    if retry_after is not None or err.status < 500:
                        break
                if isinstance(err, ValueError):
                    break
                if attempt < 2:
                    await asyncio.sleep(attempt + 1)
        self.update_interval = max(ERROR_INTERVAL, timedelta(seconds=retry_after or 0))
        _LOGGER.warning('Cannot refresh %s fuel prices: %s', self.source, error)
        return {**self.snapshot, 'last_attempt': attempted, 'ok': False,
                'last_error': str(error)}

    async def _async_fetch(self):
        """Fetch and validate one source without affecting the other source."""
        async with async_get_clientsession(self.hass).get(
            self.url, timeout=aiohttp.ClientTimeout(total=30),
            headers={'User-Agent': 'HomeAssistant-PolandFuelPrices/2.0.2'},
        ) as response:
            response.raise_for_status()
            html = await response.text()
        return await self.hass.async_add_executor_job(self.parser, html)
