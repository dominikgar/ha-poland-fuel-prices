"""Regression tests for DNS outages and source maintenance on 2026-10-21."""
import asyncio
from datetime import datetime, timedelta, timezone
import importlib.util
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest

from test_freshness import ROOT, load_coordinator, Hass, Store

spec = importlib.util.spec_from_file_location('freshness', ROOT / 'freshness.py')
freshness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(freshness)
NOW = datetime(2026, 10, 21, 19, 0, tzinfo=timezone.utc)


def coordinator():
    obj = object.__new__(load_coordinator())
    obj.hass = Hass()
    obj.source = 'market'
    obj.url = 'https://example.invalid'
    obj.snapshot = {'last_success': (NOW - timedelta(hours=9)).isoformat(),
                    'prices': {'pb': {'avg': 6.72}}}
    obj.store = Store()
    return obj


def test_maintenance_respects_retry_after_and_preserves_original_snapshot():
    obj = coordinator()
    obj._async_fetch = AsyncMock(side_effect=aiohttp.ClientResponseError(
        request_info=type('Request', (), {'real_url': obj.url})(), history=(),
        status=503, message='Service Temporarily Unavailable',
        headers={'Retry-After': '3600'}))
    before = dict(obj.snapshot)
    result = asyncio.run(obj._async_update_data())
    assert obj._async_fetch.await_count == 1
    assert obj.update_interval == timedelta(hours=1)
    assert result['last_success'] == before['last_success']
    assert obj.snapshot == before
    assert obj.store.saved is None
    assert freshness.fetch_status(result, NOW) == 'stale'


def test_temporary_dns_failure_recovers_without_waiting_an_hour():
    obj = coordinator()
    obj._async_fetch = AsyncMock(side_effect=[
        aiohttp.ClientConnectionError('DNS timed out'),
        {'prices': {'pb': {'avg': 6.70}}},
    ])
    with patch('asyncio.sleep', new_callable=AsyncMock) as sleep:
        result = asyncio.run(obj._async_update_data())
    assert obj._async_fetch.await_count == 2
    sleep.assert_awaited_once_with(1)
    assert result['ok'] is True and result['last_error'] is None
    assert obj.update_interval == timedelta(hours=1)
    assert obj.store.saved['prices']['pb']['avg'] == 6.70


def test_persistent_network_error_retries_three_times_then_every_five_minutes():
    obj = coordinator()
    obj._async_fetch = AsyncMock(side_effect=aiohttp.ClientConnectionError('offline'))
    with patch('asyncio.sleep', new_callable=AsyncMock):
        result = asyncio.run(obj._async_update_data())
    assert obj._async_fetch.await_count == 3
    assert obj.update_interval == timedelta(minutes=5)
    assert result['ok'] is False


@pytest.mark.parametrize('hours,usable,status', [(0, True, 'stale'),
    (23.9, True, 'stale'), (24, True, 'stale'), (24.01, False, 'error')])
def test_cache_has_a_strict_age_limit(hours, usable, status):
    data = {'ok': False, 'last_success': (NOW - timedelta(hours=hours)).isoformat()}
    assert freshness.usable_snapshot(data, NOW) is usable
    assert freshness.fetch_status(data, NOW) == status


@pytest.mark.parametrize('value', [None, 'not-a-date', '2026-10-21T19:00:00',
                                   '2026-10-22T19:00:00+00:00'])
def test_missing_invalid_naive_or_future_cache_timestamp_is_not_usable(value):
    assert not freshness.usable_snapshot({'last_success': value}, NOW)


@pytest.mark.parametrize('value,expected', [('3600', 3600),
    ('Wed, 21 Oct 2026 20:00:00 GMT', 3600), ('bad', None), (None, None), ('-5', 0)])
def test_retry_after_formats(value, expected):
    assert freshness.retry_after_seconds(value, NOW) == expected
