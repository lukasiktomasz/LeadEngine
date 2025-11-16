# LeadEngine

Projekt LeadEngine - system zarządzania leadami z integracją bazy danych MSSQL.

## Wymagania

- Python 3.7+
- ODBC Driver for SQL Server (pobierz z [Microsoft](https://docs.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server))
- Dostęp do serwera MSSQL

## Instalacja

1. Sklonuj repozytorium lub pobierz projekt

2. Utwórz wirtualne środowisko (opcjonalnie, ale zalecane):
```bash
python -m venv venv
```

3. Aktywuj wirtualne środowisko:
   - Windows: `venv\Scripts\activate`
   - Linux/Mac: `source venv/bin/activate`

4. Zainstaluj zależności:
```bash
pip install -r requirements.txt
```

5. Skonfiguruj połączenie z bazą danych:
   - Skopiuj plik `env.example` jako `.env`
   - Edytuj plik `.env` i uzupełnij dane do połączenia z bazą danych

6. Sprawdź konfigurację w pliku `config/config.json` (opcjonalnie)

## Uruchomienie

### Moduł Website Scraper

```bash
python -m modules.website_scraper.main
```

lub z katalogu modułu:

```bash
cd modules/website_scraper
python main.py
```

## Struktura projektu

```
LeadEngine/
├── common/                    # Część wspólna - używana przez wszystkie moduły
│   ├── logger.py              # Moduł logowania
│   ├── database.py            # Moduł połączenia z bazą danych
│   └── config.py              # Moduł odczytu konfiguracji
│
├── modules/                    # Moduły funkcjonalne
│   └── website_scraper/       # Moduł pobierania danych z witryn
│       ├── main.py            # Punkt wejścia modułu
│       ├── engine.py          # Wspólny silnik scrapowania
│       ├── base_parser.py     # Klasa bazowa dla parserów
│       ├── parsers/           # Parsery dla różnych stron
│       └── config.json        # Konfiguracja modułu
│
├── config/                    # Konfiguracja globalna
│   └── config.json            # Konfiguracja aplikacji
│
├── logs/                      # Pliki logów (tworzone automatycznie)
├── .env                       # Dane do bazy (nie commituj!)
└── requirements.txt           # Zależności Python
```

## Konfiguracja

### Plik .env

Zawiera wrażliwe dane do połączenia z bazą danych. Przykładowe opcje:

**Opcja 1: Autoryzacja SQL Server**
```
DB_SERVER=localhost
DB_DATABASE=LeadEngineDB
DB_USERNAME=sa
DB_PASSWORD=TwojeHaslo123
DB_DRIVER={ODBC Driver 17 for SQL Server}
```

**Opcja 2: Windows Authentication**
```
DB_SERVER=localhost
DB_DATABASE=LeadEngineDB
DB_TRUSTED_CONNECTION=yes
DB_DRIVER={ODBC Driver 17 for SQL Server}
```

**Opcja 3: Connection String**
```
DB_CONNECTION_STRING=DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost;DATABASE=LeadEngineDB;UID=sa;PWD=TwojeHaslo123;
```

### Plik config.json

Zawiera ogólną konfigurację aplikacji (poziomy logowania, timeouty, itp.)

## Moduły

### Część wspólna (common/)

Wszystkie moduły używają wspólnych komponentów:

```python
from common.logger import setup_logger
from common.database import DatabaseConnection, DatabaseError
from common.config import load_config, get_config_value, ConfigError

# Logger
logger = setup_logger(name="MyModule", log_file="my_module.log")
logger.info("Wiadomość informacyjna")

# Baza danych
with DatabaseConnection() as db:
    results = db.execute_query("SELECT * FROM table")

# Konfiguracja
config = load_config()
value = get_config_value(config, "app.name")
```

### Moduły funkcjonalne

#### Website Scraper (`modules/website_scraper/`)

Moduł do pobierania danych firm z witryn internetowych.

**Uruchomienie:**
```bash
python -m modules.website_scraper.main
```

**Funkcjonalność:**
- Odczytywanie listy URL-i z bazy danych
- Pobieranie zawartości stron (z retry i error handling)
- Parsowanie HTML (osobne parsery dla każdej strony)
- Zapis danych do tabeli `CRM.Company`

**Dodawanie nowego parsera:**
1. Utwórz plik w `modules/website_scraper/parsers/`
2. Dziedzicz po `BaseParser`
3. Zaimplementuj metody `get_parser_name()` i `parse()`
4. Dodaj mapowanie w `config.json`

## Bezpieczeństwo

- **NIGDY** nie commituj pliku `.env` do repozytorium
- Plik `.env` jest już dodany do `.gitignore`
- Wrażliwe dane (hasła, connection strings) tylko w `.env`
- Konfiguracja JSON zawiera tylko dane nie-wrażliwe

## Rozwiązywanie problemów

### Błąd: "ODBC Driver not found"

Zainstaluj ODBC Driver for SQL Server z oficjalnej strony Microsoft.

### Błąd: "Cannot connect to database"

1. Sprawdź czy serwer SQL jest uruchomiony
2. Sprawdź poprawność danych w pliku `.env`
3. Sprawdź czy firewall nie blokuje połączenia
4. Sprawdź czy użytkownik ma uprawnienia do bazy danych

## Licencja

[Określ licencję projektu]

