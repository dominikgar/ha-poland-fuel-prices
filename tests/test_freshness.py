"""Exercise refresh/error transitions without requiring a running HA in tests."""
import asyncio
import importlib.util
import sys
import types
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch
import aiohttp

ROOT = Path(__file__).resolve().parents[1] / 'custom_components/poland_fuel_prices'


def load_coordinator():
    modules = {}
    for name in ['homeassistant', 'homeassistant.helpers', 'homeassistant.util', 'fuel_test']:
        module = types.ModuleType(name)
        module.__path__ = []
        modules[name] = module
    for name in ['homeassistant.helpers.aiohttp_client', 'homeassistant.helpers.storage', 'homeassistant.helpers.update_coordinator', 'homeassistant.util.dt']:
        modules[name] = types.ModuleType(name)
    modules['homeassistant.helpers.aiohttp_client'].async_get_clientsession = lambda hass: hass.session
    modules['homeassistant.helpers.storage'].Store = object
    modules['homeassistant.helpers.update_coordinator'].DataUpdateCoordinator = object
    modules['homeassistant.util.dt'].utcnow = lambda: datetime.now(timezone.utc)
    with patch.dict(sys.modules, modules):
        for name in ['parser', 'freshness', 'coordinator']:
            spec = importlib.util.spec_from_file_location('fuel_test.' + name, ROOT / (name + '.py'))
            module = importlib.util.module_from_spec(spec)
            sys.modules['fuel_test.' + name] = module
            spec.loader.exec_module(module)
        result = sys.modules['fuel_test.coordinator'].FuelCoordinator
    sys.modules.pop('fuel_test.parser', None)
    sys.modules.pop('fuel_test.freshness', None)
    sys.modules.pop('fuel_test.coordinator', None)
    return result


class Session:
    def __init__(self, fail=False):
        self.fail = fail
    def get(self, *args, **kwargs):
        return self
    async def __aenter__(self):
        if self.fail:
            raise aiohttp.ClientConnectionError('test outage')
        return self
    async def __aexit__(self, *args):
        pass
    def raise_for_status(self):
        pass
    async def text(self):
        return 'valid test page'


class Store:
    def __init__(self):
        self.saved = None
    async def async_save(self, data):
        self.saved = data


class Hass:
    def __init__(self):
        self.session = Session()
    async def async_add_executor_job(self, fn, arg):
        return fn(arg)


def test_outage_does_not_advance_last_success_and_recovery_clears_error():
    cls = load_coordinator()
    coordinator = object.__new__(cls)
    coordinator.hass = Hass()
    coordinator.source = 'market'
    coordinator.url = 'https://example.invalid'
    coordinator.parser = lambda text: {'prices': {'pb': {'avg': 6.72}}}
    coordinator.snapshot = {}
    coordinator.store = Store()
    async def run():
        good = await coordinator._async_update_data()
        assert good['ok'] and good['last_success']
        timestamp = good['last_success']
        coordinator.hass.session.fail = True
        with patch('asyncio.sleep', new_callable=AsyncMock):
            failed = await coordinator._async_update_data()
        assert failed['ok'] is False
        assert failed['last_success'] == timestamp
        assert failed['last_error'] == 'test outage'
        assert failed['last_attempt'] >= good['last_attempt']
        assert failed['prices'] == good['prices']
        coordinator.hass.session.fail = False
        recovered = await coordinator._async_update_data()
        assert recovered['ok'] and recovered['last_error'] is None
        assert recovered['last_success'] > timestamp
    asyncio.run(run())


def test_parser_failure_preserves_saved_data():
    cls = load_coordinator()
    coordinator = object.__new__(cls)
    coordinator.hass = Hass()
    coordinator.source = 'government'
    coordinator.url = 'https://example.invalid'
    coordinator.snapshot = {'last_success': '2026-10-12T12:00:00+00:00', 'records': [{'valid_from': '2026-10-12'}]}
    coordinator.store = Store()
    def parser(text):
        raise ValueError('format changed')
    coordinator.parser = parser
    result = asyncio.run(coordinator._async_update_data())
    assert result['ok'] is False
    assert result['last_success'] == '2026-10-12T12:00:00+00:00'
    assert result['records'] == coordinator.snapshot['records']
    assert coordinator.store.saved is None
