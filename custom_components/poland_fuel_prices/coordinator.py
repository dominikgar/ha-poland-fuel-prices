"""Independent polling and honest freshness reporting for each source."""
from datetime import timedelta
import logging
import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util
from .parser import GOV_URL, MARKET_URL, parse_government, parse_market

_LOGGER = logging.getLogger(__name__)

class FuelCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry, source):
        super().__init__(hass, _LOGGER, name=f'Poland fuel prices {source}',
                         config_entry=entry, update_interval=timedelta(hours=1))
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
        try:
            async with async_get_clientsession(self.hass).get(
                self.url, timeout=aiohttp.ClientTimeout(total=30),
                headers={'User-Agent': 'HomeAssistant-PolandFuelPrices/2.0'},
            ) as response:
                response.raise_for_status()
                html = await response.text()
            parsed = await self.hass.async_add_executor_job(self.parser, html)
            self.snapshot = {**parsed, 'last_success': dt_util.utcnow().isoformat()}
            await self.store.async_save(self.snapshot)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            _LOGGER.warning('Cannot refresh %s fuel prices: %s', self.source, err)
            return {**self.snapshot, 'last_attempt': attempted, 'ok': False,
                    'last_error': str(err)}
        return {**self.snapshot, 'last_attempt': attempted, 'ok': True, 'last_error': None}
