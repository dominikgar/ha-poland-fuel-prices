# Changelog

## 2.0.2 — 2026-10-21

- Retry transient network/DNS failures, recover every five minutes after outages and respect HTTP Retry-After during source maintenance.
- Show cached prices for at most 24 hours, explicitly marked stale, without advancing the successful-fetch timestamp; government validity dates still apply.
- Fetch both sources concurrently at startup and midnight; one source's outage does not suppress the other source's data.
- Report actual polling interval and cached-data age; add outage regression tests.

## 2.0.1 — 2026-10-12

- HACS custom repository packaging, installation instructions and English setup translations.
- Public dashboard example and automated parser/freshness tests.
- Keeps the integration domain and existing entity IDs from 2.0.0.

## 2.0.0 — 2026-10-12

- Native Home Assistant config flow with independent hourly polling for each source.
- National and regional fuel price averages from AutoCentrum.
- Official current and announced government limits with explicit validity dates.
- Successful fetch and attempt timestamps, source status, cached last successful data, and manual refresh.
