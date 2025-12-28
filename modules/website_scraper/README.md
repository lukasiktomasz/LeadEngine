# Moduł Website Scraper

Moduł do pobierania danych firm (wystawców) z witryn targów i wystaw.

## Opis

Moduł `website_scraper` pobiera dane z serwisu **targikielce.pl**:

1. Pobiera listę wydarzeń (targów) z API kalendarza
2. Filtruje tylko przyszłe wydarzenia
3. Dla każdego wydarzenia pobiera listę wystawców (firm)
4. Sprawdza duplikaty - dodaje tylko nowe firmy
5. Zapisuje dane do bazy `CRM.Event` i `CRM.Company`

## Struktura

```
website_scraper/
├── main.py              # Punkt wejścia modułu
├── engine.py            # Silnik HTTP (fetch, retry, JSON)
├── base_parser.py       # Klasa bazowa dla parserów
├── parsers/
│   ├── targi_kielce.py  # Parser dla targikielce.pl
│   └── example_site.py  # Szablon do tworzenia nowych parserów
├── config.json          # Konfiguracja modułu
└── README.md            # Ten plik
```

## Uruchomienie

Z katalogu głównego projektu:

```bash
python -m modules.website_scraper.main
```

lub bezpośrednio:

```bash
cd modules/website_scraper
python main.py
```

## Jak działa

### 1. Pobieranie wydarzeń
- API: `https://www.targikielce.pl/api/modules/trades/search/1/60`
- Zwraca HTML z listą wydarzeń
- Parsuje: nazwa, data, URL, opis

### 2. Sprawdzanie wystawców
- Dla każdego wydarzenia generuje URL: `/lista-wystawcow`
- Pobiera ustawienia Vue.js z `v-init:settings`
- Sprawdza `pager.rowCount` - liczbę wystawców

### 3. Wykrywanie duplikatów
- Porównuje liczbę firm w bazie z API
- Jeśli `db_count >= api_count` → pomija (bez zmian)
- Jeśli `db_count < api_count` → pobiera tylko nowe

### 4. Paginacja
- API używa `pageIndex` (1, 2, 3, ...)
- 25 wystawców na stronę
- Pełne parametry: `?pageIndex=X&sort[field]=title&count=Y`

## Konfiguracja

Plik `config.json`:

```json
{
  "scraping": {
    "max_retries": 3,
    "timeout": 30,
    "delay_between_requests": 1.0,
    "filter_future_events": true
  },
  "mapping": {
    "default_country_id": 1,
    "default_industry_id": 1
  }
}
```

## Zapisywane dane

### Tabela `CRM.Event`
| Pole | Opis |
|------|------|
| Name | Nazwa wydarzenia (max 50 znaków) |
| EventDate | Data wydarzenia |
| WWW | URL wydarzenia |
| DataSourceId | ID źródła (Targi Kielce) |

### Tabela `CRM.Company`
| Pole | Opis |
|------|------|
| Name | Nazwa firmy (max 250 znaków) |
| EventId | ID powiązanego wydarzenia |
| CountryId | ID kraju (mapowany z nazwy) |
| IndustryId | ID branży (domyślna wartość) |
| CompanyEventLink | Link do strony firmy w ramach wydarzenia |
| Description | Opis (opcjonalnie) |
| Address | Adres (opcjonalnie) |
| Phone | Telefon (opcjonalnie) |
| Email | Email (opcjonalnie) |
| WWW | Strona WWW (opcjonalnie) |

> **Uwaga:** `ContactDataSourceId` jest ustawiane dopiero gdy pobierzemy dane kontaktowe ze strony szczegółów firmy.

## Dodawanie nowego parsera

1. Utwórz plik w `parsers/`, np. `nowa_strona.py`
2. Dziedzicz po `BaseParser`
3. Zaimplementuj:
   - `get_parser_name()` - nazwa parsera
   - `get_events(engine)` - lista wydarzeń
   - `get_exhibitors(url, engine)` - lista wystawców
4. Zaimportuj w `main.py`

## Przykład użycia

```python
from modules.website_scraper.main import WebsiteScraperModule

module = WebsiteScraperModule()
module.run()
```

## Logi

Logi zapisywane są do:
- `logs/website_scraper.log` - szczegółowe logi modułu
- Konsola - podsumowanie z kolorami
