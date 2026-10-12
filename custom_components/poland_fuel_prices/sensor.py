"""Prices, source timestamps and fetch status."""
from datetime import datetime
from zoneinfo import ZoneInfo
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .parser import FUELS, select_record

PARALLEL_UPDATES = 0

async def async_setup_entry(hass, entry, async_add_entities):
    entities = []
    for source, coordinator in entry.runtime_data.items():
        metrics = ('avg', 'regional_min', 'regional_max') if source == 'market' else ('gov_max', 'gov_next')
        fuels = FUELS if source == 'market' else ('pb', 'pbp', 'on')
        entities.extend(FuelSensor(coordinator, code, metric) for code in fuels for metric in metrics)
        entities.extend(SourceSensor(coordinator, metric) for metric in ('last_success', 'last_attempt', 'status'))
    async_add_entities(entities)

class FuelBase(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_device_info = {'identifiers': {('poland_fuel_prices', coordinator.source)},
                                 'name': 'Ceny paliw — ' + ('Ministerstwo Energii' if coordinator.source == 'government' else 'AutoCentrum'),
                                 'manufacturer': 'gov.pl' if coordinator.source == 'government' else 'AutoCentrum.pl'}

class FuelSensor(FuelBase):
    _attr_native_unit_of_measurement = 'zł/l'
    _attr_icon = 'mdi:gas-station'
    _attr_suggested_display_precision = 2
    def __init__(self, coordinator, code, metric):
        super().__init__(coordinator)
        self.code, self.metric = code, metric
        labels = {'avg': 'średnia krajowa', 'regional_min': 'najniższa średnia wojewódzka',
                  'regional_max': 'najwyższa średnia wojewódzka', 'gov_max': 'limit obowiązujący',
                  'gov_next': 'limit zapowiedziany'}
        self._attr_name = f'{FUELS[code]} {labels[metric]}'
        self._attr_unique_id = f'poland_fuel_prices_{code}_{metric}'
        self.entity_id = f'sensor.poland_fuel_prices_{code}_{metric}'

    def _record(self):
        return select_record((self.coordinator.data or {}).get('records', []),
                             datetime.now(ZoneInfo('Europe/Warsaw')).date(), self.metric == 'gov_next')

    @property
    def available(self):
        data = self.coordinator.data or {}
        if not data.get('ok'):
            return False
        if self.coordinator.source == 'government':
            return self.metric == 'gov_next' or self._record() is not None
        return data.get('prices', {}).get(self.code, {}).get(self.metric) is not None

    @property
    def native_value(self):
        if self.coordinator.source == 'market':
            return (self.coordinator.data or {}).get('prices', {}).get(self.code, {}).get(self.metric)
        record = self._record()
        return record['prices'][self.code] if record else None

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or {}
        attrs = {k: data.get(k) for k in ('source_url', 'last_attempt', 'last_success', 'last_error')}
        attrs['data_status'] = 'ok' if data.get('ok') else 'fetch_error'
        if self.coordinator.source == 'market':
            attrs['source_updated_text'] = data.get('source_updated_text')
            attrs['meaning'] = 'Średnia krajowa' if self.metric == 'avg' else 'Ekstremum średnich wojewódzkich; nie cena konkretnej stacji'
            item = data.get('prices', {}).get(self.code, {})
            attrs['regions_count'] = item.get('regions_count')
            if self.metric != 'avg':
                attrs['regions'] = item.get(self.metric + '_regions', [])
        else:
            record = self._record()
            if record:
                attrs.update({k: record[k] for k in ('source_url', 'announcement_url', 'valid_from', 'valid_to', 'published_on')})
            attrs['meaning'] = 'Oficjalny limit zapowiedziany; nie prognoza' if self.metric == 'gov_next' else 'Oficjalny limit z podanym okresem obowiązywania'
        return attrs

class SourceSensor(FuelBase):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    def __init__(self, coordinator, metric):
        super().__init__(coordinator)
        self.metric = metric
        self._attr_unique_id = f'poland_fuel_prices_{coordinator.source}_{metric}'
        self.entity_id = f'sensor.poland_fuel_prices_{coordinator.source}_{metric}'
        self._attr_name = {'last_success': 'Ostatnie udane pobranie', 'last_attempt': 'Ostatnia próba odświeżenia', 'status': 'Status pobierania'}[metric]
        if metric != 'status':
            self._attr_device_class = SensorDeviceClass.TIMESTAMP
    @property
    def available(self):
        return True
    @property
    def native_value(self):
        data = self.coordinator.data or {}
        if self.metric == 'status':
            return 'ok' if data.get('ok') else 'error'
        value = data.get(self.metric)
        return datetime.fromisoformat(value) if value else None
    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or {}
        return {'source_url': self.coordinator.url, 'last_error': data.get('last_error'), 'refresh_interval_minutes': 60}
