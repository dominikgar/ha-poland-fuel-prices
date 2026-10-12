from pathlib import Path
from datetime import date
import importlib.util
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('fuel_parser', ROOT / 'custom_components/poland_fuel_prices/parser.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
MARKET = (ROOT / 'tests/market.html').read_text()
GOV = (ROOT / 'tests/government.html').read_text()


def test_market_real_page():
    data = p.parse_market(MARKET)
    assert set(data['prices']) == set(p.FUELS)
    assert data['prices']['pb']['avg'] == 6.72
    assert data['prices']['pb']['regional_max'] == 7.1
    assert data['prices']['pb']['regional_max_regions'] == ['świętokrzyskie']
    assert data['prices']['onp']['regions_count'] == 10
    assert data['source_updated_text'] == '24h temu'


def test_missing_table_rejected():
    with pytest.raises(ValueError):
        p.parse_market(MARKET.replace('petrols-table', 'changed-table'))


def test_missing_fuel_rejected():
    with pytest.raises(ValueError):
        p.parse_market(MARKET.replace('station-detail-wrapper pbp', 'changed-wrapper pbp'))


def test_no_fabricated_regional_price():
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(MARKET, 'html.parser')
    for row in soup.select('table.petrols-table tbody tr'):
        row.find_all('td')[1].string = '-'
    data = p.parse_market(str(soup))['prices']['pb']
    assert data['avg'] == 6.72
    assert data['regional_min'] is None
    assert data['regional_max'] is None


def test_government_current_and_announced_separate():
    records = p.parse_government(GOV)['records']
    current = p.select_record(records, date(2026, 10, 12))
    future = p.select_record(records, date(2026, 10, 12), True)
    assert current['prices'] == {'pb': 6.97, 'pbp': 7.85, 'on': 8.06}
    assert current['valid_to'] == '2026-10-12'
    assert future['prices'] == {'pb': 7.06, 'pbp': 7.95, 'on': 8.02}
    assert future['valid_from'] == '2026-10-13'


def test_next_day_promotes_announced():
    records = p.parse_government(GOV)['records']
    assert p.select_record(records, date(2026, 10, 13))['prices']['pb'] == 7.06
    assert p.select_record(records, date(2026, 10, 13), True) is None


def test_expired_limit_not_extended():
    records = p.parse_government(GOV)['records']
    assert p.select_record(records, date(2026, 10, 14)) is None


def test_weekend_range_boundaries():
    records = p.parse_government(GOV)['records']
    for day in (10, 11, 12):
        assert p.select_record(records, date(2026, 10, day))['prices']['pb'] == 6.97
    assert p.select_record(records, date(2026, 10, 9))['prices']['pb'] == 6.90


@pytest.mark.parametrize('title', ['obowiązująca jutro', 'obowiązująca 12 niewiadomo 2026 r.', 'obowiązująca w dniach 12-10 października 2026 r.'])
def test_bad_dates_fail_closed(title):
    with pytest.raises(ValueError):
        p.effective_dates(title)


def test_changed_price_format_fails_closed():
    with pytest.raises(ValueError):
        p.parse_government(GOV.replace('7,06 zł/l', '7,06 EUR/l'))


def test_no_announcements_rejected():
    with pytest.raises(ValueError):
        p.parse_government('<html>Service temporarily unavailable</html>')
