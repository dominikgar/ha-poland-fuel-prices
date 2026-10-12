"""Manual refresh of both sources."""
import asyncio
from homeassistant.components.button import ButtonEntity

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([RefreshButton(entry)])

class RefreshButton(ButtonEntity):
    _attr_name = 'Ceny paliw — odśwież dane'
    _attr_unique_id = 'poland_fuel_prices_refresh'
    _attr_icon = 'mdi:refresh'
    def __init__(self, entry):
        self.entry = entry
        self.entity_id = 'button.poland_fuel_prices_refresh'
    async def async_press(self):
        await asyncio.gather(*(c.async_request_refresh() for c in self.entry.runtime_data.values()))
