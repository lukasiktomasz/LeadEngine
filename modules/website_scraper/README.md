# Moduł Website Scraper

Moduł do pobierania danych firm z witryn internetowych.

## Opis

Moduł `website_scraper` jest odpowiedzialny za:
1. Odczytywanie listy adresów URL z bazy danych
2. Pobieranie zawartości stron internetowych
3. Parsowanie HTML i ekstrakcję danych firm
4. Zapis danych do bazy danych `CRM.Company`

## Struktura

```
website_scraper/
├── main.py              # Punkt wejścia modułu
├── engine.py            # Wspólny silnik scrapowania (HTTP, retry, error handling)
├── base_parser.py       # Klasa bazowa dla parserów
├── parsers/             # Osobne parsery dla każdej strony źródłowej
│   ├── targi_kielce.py  # Parser dla targikielce.pl
│   └── example_site.py  # Przykładowy parser (szablon)
├── config.json          # Konfiguracja modułu
└── README.md            # Ten plik
```

## Uruchomienie

```bash
python -m modules.website_scraper.main
```

lub z katalogu głównego projektu:

```bash
cd modules/website_scraper
python main.py
```

## Konfiguracja

Edytuj plik `config.json` aby dostosować:
- Parametry scrapowania (retry, timeout, delay)
- Mapowanie tabel i kolumn w bazie danych
- Mapowanie parserów dla różnych domen
- Wartości domyślne (CountryId, IndustryId, ContactDataSourceId)

## Dodawanie nowego parsera

1. Utwórz nowy plik w katalogu `parsers/`, np. `moja_strona.py`
2. Dziedzicz po klasie `BaseParser`
3. Zaimplementuj metody:
   - `get_parser_name()` - zwraca nazwę parsera
   - `parse(html_content, url)` - parsuje HTML i zwraca dane firmy
4. Dodaj mapowanie w `config.json`:
   ```json
   "parser_mapping": {
     "moja-strona.pl": "moja_strona"
   }
   ```
5. Zaimportuj parser w `main.py`

## Format danych zwracanych przez parser

Parser powinien zwracać słownik z następującymi kluczami:
- `name` (wymagane) - nazwa firmy
- `address` - adres
- `phone` - telefon
- `email` - email
- `www` - strona internetowa
- `description` - opis firmy

## Wykorzystanie bazy danych

Moduł zapisuje dane do tabeli `CRM.Company` z następującymi polami:
- Name - nazwa firmy
- Address - adres
- Phone - telefon
- Email - email
- WWW - strona internetowa
- Description - opis
- EventId - ID wydarzenia (z tabeli źródłowej)
- IndustryId - ID branży (z konfiguracji)
- CountryId - ID kraju (z konfiguracji)
- ContactDataSourceId - ID źródła danych (z konfiguracji)

