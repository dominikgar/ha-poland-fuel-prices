"""Polish market prices and official announced fuel price limits."""
import asyncio
from homeassistant.const import Platform
from homeassistant.helpers.event import async_track_time_change
from .coordinator import FuelCoordinator

DOMAIN = 'poland_fuel_prices'
PLATFORMS = [Platform.SENSOR, Platform.BUTTON]

async def async_setup_entry(hass, entry):
    coordinators = {source: FuelCoordinator(hass, entry, source)
                    for source in ('market', 'government')}
    await asyncio.gather(*(coordinator.async_config_entry_first_refresh()
                           for coordinator in coordinators.values()))
    entry.runtime_data = coordinators
    # Recompute validity on local midnight even if price values have not changed.
    async def midnight(now):
        await asyncio.gather(*(coordinator.async_request_refresh()
                               for coordinator in coordinators.values()))
    entry.async_on_unload(async_track_time_change(hass, midnight, hour=0, minute=0, second=5))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass, entry):
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
