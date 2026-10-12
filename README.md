# Poland Fuel Prices — ceny paliw w Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories/)

Custom component dla Home Assistanta: średnie ceny paliw w Polsce oraz oficjalne, obowiązujące i zapowiedziane limity cen. Działa na serwerze HA, bez dodatkowego komputera, crona i tokenu dostępu.

English: A Home Assistant custom integration for Polish national/regional fuel price averages and official current/announced government price caps. Hourly polling, independent source status, fetch timestamps and manual refresh.

## Instalacja przez HACS

Wymagany Home Assistant **2026.10.0 lub nowszy**. Działanie sprawdzono na 2026.10.1.

1. Otwórz HACS → menu ⋮ → **Custom repositories / Niestandardowe repozytoria**.
2. Dodaj `https://github.com/dominikgar/ha-poland-fuel-prices` jako kategorię **Integration**.
3. Wyszukaj **Poland Fuel Prices** i wybierz pobranie instalacji.
4. Zrestartuj Home Assistanta.
5. Otwórz **Ustawienia → Urządzenia i usługi → Dodaj integrację → Poland Fuel Prices** i potwierdź.

To repozytorium niestandardowe HACS. Nie jest częścią domyślnego katalogu HACS. Gdy repozytorium nie ma wydania GitHub Release, HACS instaluje kod z domyślnej gałęzi `main`.

Jeżeli komponent 2.0.0 został wcześniej skopiowany ręcznie, pobierz go przez HACS i zrestartuj HA. Pozostaw dotychczasowy wpis integracji — domena i identyfikatory encji są zachowane. Nie dodawaj drugiej integracji ani starego wpisu `sensor: - platform: poland_fuel_prices` do YAML.

## Co pokazuje integracja

| Źródło | Paliwa | Dane |
| --- | --- | --- |
| [AutoCentrum](https://www.autocentrum.pl/paliwa/ceny-paliw/) | Pb95, Pb98, ON, ON+, LPG | Średnia krajowa oraz najniższa i najwyższa **średnia wojewódzka** |
| [Ministerstwo Energii](https://www.gov.pl/web/energia/wiadomosci) | Pb95, Pb98, ON | Oficjalny limit obowiązujący oraz najbliższy limit zapowiedziany z datami obowiązywania |

Regionalne minimum i maksimum nie oznaczają najtańszej i najdroższej stacji w Polsce. Atrybut `regions` pokazuje województwa odpowiadające skrajnej średniej. Zapowiedziana stawka rządowa jest opublikowanym limitem na przyszły okres, nie prognozą analityczną.

Integracja pobiera listę wiadomości ministerstwa i odczytuje kompletną stawkę, tytuł, datę publikacji oraz jawnie podany okres obowiązywania z zajawki danego komunikatu. `source_url` wskazuje pobraną stronę, a `announcement_url` prowadzi do komunikatu.

## Aktualność i błędy

Każde źródło jest sprawdzane niezależnie **co godzinę**, dodatkowo o lokalnej północy HA i przyciskiem `button.poland_fuel_prices_refresh`.

- `last_success` — ostatnie udane pobranie i rozpoznanie danych.
- `last_attempt` — ostatnia próba odświeżenia, również nieudana.
- `last_error` i status `ok` / `error` — wynik sprawdzenia źródła.
- `source_updated_text` — informacja AutoCentrum o aktualizacji jego danych, jeśli jest dostępna.
- `published_on`, `valid_from`, `valid_to` — daty publikacji i obowiązywania limitów.

Czas pobrania strony nie jest datą aktualizacji danych u wydawcy. Znaczniki czasu są zapisywane ze strefą UTC, a interfejs HA wyświetla je lokalnie. Okres obowiązywania polskich limitów jest liczony według `Europe/Warsaw`.

Po błędzie źródła jego sensory cen stają się `unavailable`. Ostatnie poprawne dane i rzeczywisty czas ich pobrania pozostają w pamięci podręcznej, także po restarcie. Błąd nie nadaje im nowej daty sukcesu. Brak przyszłego komunikatu daje `unknown` dla limitu zapowiedzianego. Brak komunikatu obejmującego dzisiejszą datę daje `unavailable` dla limitu aktualnego. Komponent nie przedłuża samodzielnie ważności historycznych stawek.

## Encje

Łącznie **27 sensorów i jeden przycisk**:

| Identyfikator | Znaczenie |
| --- | --- |
| `sensor.poland_fuel_prices_<paliwo>_avg` | Średnia krajowa |
| `sensor.poland_fuel_prices_<paliwo>_regional_min` | Najniższa średnia wojewódzka |
| `sensor.poland_fuel_prices_<paliwo>_regional_max` | Najwyższa średnia wojewódzka |
| `sensor.poland_fuel_prices_<paliwo>_gov_max` | Limit obowiązujący |
| `sensor.poland_fuel_prices_<paliwo>_gov_next` | Limit zapowiedziany |
| `sensor.poland_fuel_prices_<źródło>_last_success` | Ostatnie udane pobranie |
| `sensor.poland_fuel_prices_<źródło>_last_attempt` | Ostatnia próba odświeżenia |
| `sensor.poland_fuel_prices_<źródło>_status` | Status pobierania |
| `button.poland_fuel_prices_refresh` | Odśwież oba źródła |

Kody paliw: `pb` (Pb95), `pbp` (Pb98), `on`, `onp` (ON+) i `lpg`. Limity rządowe mają sensory dla `pb`, `pbp`, `on`. Kody źródeł: `market`, `government`.

## Przykład panelu

W [examples/dashboard.json](examples/dashboard.json) jest gotowy przykład natywnego kokpitu HA z cenami, datami i statusem źródeł. Utwórz pusty panel, otwórz jego edytor konfiguracji i wklej zawartość pliku — JSON jest poprawnym formatem YAML. Panel jest opcjonalny i nie jest automatycznie tworzony przez integrację.

## Instalacja ręczna

Skopiuj `custom_components/poland_fuel_prices` do `/config/custom_components/`, zrestartuj HA i dodaj integrację w ustawieniach. Nie uruchamiaj równolegle starego skryptu demonstracyjnego, który wysyłał stałe ceny przez API.

## Ograniczenia

Oba źródła są odczytywane z HTML. Zmiana struktury stron może wymagać aktualizacji parsera. Integracja korzysta z pierwszej strony wiadomości ministerstwa; jeżeli zniknie z niej komunikat obejmujący bieżący dzień, nie będzie przedstawiać historycznej stawki jako aktualnej. Niekompletne dane są odrzucane. Nie są generowane ceny demonstracyjne ani własne prognozy.

## Rozwój i testy

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest tests -q
```

Testy obejmują parsowanie, zakresy dat i weekendów, przejście zapowiedzi na obowiązujący limit, wygaśnięcie limitów oraz obsługę awarii bez zmiany czasu ostatniego sukcesu. Niewielkie pliki HTML są zsyntetyzowanymi przykładami struktury źródeł; nie wymagają dostępu do sieci ani HA.

GitHub Actions uruchamia testy, walidację HACS oraz hassfest. Zmiany i wersje są opisane w [CHANGELOG.md](CHANGELOG.md). Błędy można zgłaszać w [Issues](https://github.com/dominikgar/ha-poland-fuel-prices/issues).

## Licencja

Kod i własne zasoby graficzne: [MIT](LICENSE). Projekt jest niezależny od AutoCentrum, Ministerstwa Energii i HACS. Dane pochodzą ze wskazanych serwisów.
