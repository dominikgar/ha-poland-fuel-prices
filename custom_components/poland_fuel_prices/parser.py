"""Strict parsers for public fuel price pages; no invented prices or dates."""
from __future__ import annotations
from datetime import date
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup

MARKET_URL = 'https://www.autocentrum.pl/paliwa/ceny-paliw/'
GOV_URL = 'https://www.gov.pl/web/energia/wiadomosci'
FUELS = {'pb': 'Pb95', 'pbp': 'Pb98', 'on': 'ON', 'onp': 'ON+', 'lpg': 'LPG'}
MONTHS = dict(zip(('stycznia lutego marca kwietnia maja czerwca lipca sierpnia września października listopada grudnia').split(), range(1, 13)))


def price(text):
    match = re.fullmatch(r'\s*(\d{1,2}[,.]\d{2})\s*(?:zł(?:/l)?)?\s*', text)
    if not match:
        raise ValueError('Unrecognized price')
    value = float(match[1].replace(',', '.'))
    if not 0.1 <= value <= 30:
        raise ValueError('Price outside plausible range')
    return value


def parse_market(html):
    soup = BeautifulSoup(html, 'html.parser')
    values = {}
    for a in soup.select('a.station-detail-wrapper'):
        codes = set(a.get('class', [])) & FUELS.keys()
        node = a.select_one('.price')
        if len(codes) == 1 and node:
            values[codes.pop()] = {'avg': price(node.get_text(' ', strip=True))}
    if set(values) != set(FUELS):
        raise ValueError('Missing national prices: page structure may have changed')
    table = soup.select_one('table.petrols-table')
    if table is None:
        raise ValueError('Regional price table missing')
    columns = []
    for th in table.select('thead th')[1:]:
        node = th.select_one('.fuel-logo')
        codes = set(node.get('class', [])) & FUELS.keys() if node else set()
        if len(codes) != 1:
            raise ValueError('Unknown regional table column')
        columns.append(codes.pop())
    if set(columns) != set(FUELS):
        raise ValueError('Incomplete regional table headers')
    regions = {f: [] for f in FUELS}
    for row in table.select('tbody tr'):
        cells = row.find_all('td', recursive=False)
        if len(cells) != len(columns) + 1:
            continue
        region = cells[0].get_text(' ', strip=True)
        if region.casefold() == 'polska':
            continue
        for code, cell in zip(columns, cells[1:]):
            text = cell.get_text(' ', strip=True)
            if text in ('', '-', '—'):
                continue
            regions[code].append((price(text), region))
    for code, entries in regions.items():
        values[code]['regional_min'] = min((v for v, _ in entries), default=None)
        values[code]['regional_max'] = max((v for v, _ in entries), default=None)
        values[code]['regions_count'] = len(entries)
        for metric in ('regional_min', 'regional_max'):
            values[code][metric + '_regions'] = [r for v, r in entries if v == values[code][metric]]
    text = soup.get_text(' ', strip=True)
    updated = re.search(r'Ostatnia aktualizacja\s+(.{1,60}?)\s+(?:Średnie ceny|Stacje Paliw)', text)
    return {'prices': values, 'source_url': MARKET_URL,
            'source_updated_text': updated[1].strip() if updated else None}


def effective_dates(title):
    # Only explicit single-day or same-month ranges. Never infer a legal interval.
    match = re.search(r'obowiązując\w*\s+(?:w\s+dniach\s+)?(\d{1,2})(?:\s*[-–—]\s*(\d{1,2}))?\s+([a-ząćęłńóśźż]+)\s+(\d{4})', title.casefold())
    if not match or match[3] not in MONTHS:
        raise ValueError('Missing explicit validity dates')
    start = date(int(match[4]), MONTHS[match[3]], int(match[1]))
    end = date(int(match[4]), MONTHS[match[3]], int(match[2] or match[1]))
    if end < start:
        raise ValueError('Reversed validity range')
    return start.isoformat(), end.isoformat()


def parse_government(html):
    soup = BeautifulSoup(html, 'html.parser')
    records = []
    errors = 0
    seen = set()
    for a in soup.select('a[href*="/web/energia/maksymalna-cena-detaliczna-paliw-"]'):
        url = urljoin(GOV_URL, a['href'])
        if url in seen:
            continue
        seen.add(url)
        item = a.find_parent('li')
        if item is None:
            continue
        try:
            start, end = effective_dates(a.get_text(' ', strip=True))
            intro = item.select_one('.intro')
            text = intro.get_text(' ', strip=True) if intro else ''
            prices = {}
            for code, label in [('pb', r'benzyna\s+95'), ('pbp', r'benzyna\s+98'), ('on', r'olej\s+napędowy')]:
                matches = re.findall(label + r'\s*[-–—:]\s*(\d{1,2}[,.]\d{2})\s*zł/l', text, re.I)
                if len(set(matches)) != 1:
                    raise ValueError('Missing or conflicting government prices')
                prices[code] = price(matches[0])
            published = item.select_one('.date')
            published = published.get_text(strip=True) if published else None
            if published:
                d, m, y = published.split('.')
                published = date(int(y), int(m), int(d)).isoformat()
                if published > start:
                    raise ValueError('Publication after validity start')
            records.append({'valid_from': start, 'valid_to': end, 'published_on': published,
                            'prices': prices, 'source_url': GOV_URL, 'announcement_url': url,
                            'title': a.get_text(' ', strip=True)})
        except (ValueError, AttributeError):
            errors += 1
    if not records or errors:
        raise ValueError(f'Incomplete government announcements ({errors} invalid, {len(records)} parsed)')
    return {'records': records, 'source_url': GOV_URL}


def select_record(records, today, future=False):
    day = today.isoformat()
    candidates = [r for r in records if (r['valid_from'] > day if future else r['valid_from'] <= day <= r['valid_to'])]
    if not candidates:
        return None
    if future:
        return min(candidates, key=lambda r: (r['valid_from'], r['published_on'] or ''))
    return max(candidates, key=lambda r: (r['published_on'] or '', r['valid_from']))
