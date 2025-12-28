"""
Główny plik modułu website_scraper
Punkt wejścia do uruchomienia modułu
"""

import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

# Dodaj katalog główny do ścieżki
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from common.base_module import BaseModule
from common.database import DatabaseError

# Import zależny od sposobu uruchomienia
try:
    from .engine import ScrapingEngine
    from .parsers.targi_kielce import TargiKielceParser
except ImportError:
    # Uruchomienie bezpośrednie z katalogu modułu
    import sys
    from pathlib import Path
    module_dir = Path(__file__).parent
    if str(module_dir) not in sys.path:
        sys.path.insert(0, str(module_dir))
    from engine import ScrapingEngine
    from parsers.targi_kielce import TargiKielceParser


class WebsiteScraperModule(BaseModule):
    """Moduł do pobierania danych firm z witryn internetowych"""
    
    def __init__(self):
        # Ścieżka do konfiguracji względem tego pliku
        config_path = Path(__file__).parent / "config.json"
        super().__init__(
            module_name="WebsiteScraper",
            module_config_path=str(config_path.absolute()),
            log_file="website_scraper.log"
        )
        self.engine: Optional[ScrapingEngine] = None
        self.parser: Optional[TargiKielceParser] = None
    
    def _init_module(self) -> bool:
        """Inicjalizacja silnika scrapowania i parsera"""
        try:
            max_retries = self.get_config_value("scraping.max_retries", 3)
            timeout = self.get_config_value("scraping.timeout", 30)
            delay = self.get_config_value("scraping.delay_between_requests", 1.0)
            
            self.engine = ScrapingEngine(
                self.logger,
                max_retries=max_retries,
                timeout=timeout,
                delay=delay
            )
            
            self.parser = TargiKielceParser(self.logger)
            
            self.logger.info("<green>Silnik scrapowania zainicjalizowany</green>")
            return True
            
        except Exception as e:
            self.logger.error(f"<red>Błąd inicjalizacji silnika scrapowania: {e}</red>")
            return False
    
    def _cleanup_module(self) -> None:
        """Zamykanie silnika scrapowania"""
        if self.engine:
            self.engine.close()
    
    def execute(self) -> bool:
        """
        Główna logika modułu - scrapowanie danych z targikielce.pl
        """
        # Test połączenia z bazą danych
        if not self.db.test_connection():
            self.logger.error("<red>Brak połączenia z bazą danych</red>")
            return False
        
        self.logger.info("<green>Połączenie z bazą danych: OK</green>")
        
        # Upewnij się, że mamy wpis w Dictionary.DataSource dla targikielce.pl
        data_source_id = self._ensure_data_source()
        if not data_source_id:
            self.logger.error("<red>Nie udało się utworzyć/pobrać źródła danych</red>")
            return False
        
        # Pobierz listę wydarzeń
        events = self.parser.get_events(self.engine)
        
        if not events:
            self.logger.warning("<yellow>Nie znaleziono żadnych wydarzeń</yellow>")
            return True
        
        # Filtruj tylko przyszłe wydarzenia (opcjonalne)
        filter_future = self.get_config_value("scraping.filter_future_events", True)
        if filter_future:
            events = self._filter_future_events(events)
            self.logger.info(f"<cyan>Przyszłe wydarzenia: {len(events)}</cyan>")
        
        # Przetwarzaj każde wydarzenie
        total_exhibitors = 0
        processed_events = 0
        skipped_events = 0
        
        for event in events:
            try:
                self.logger.info(f"<cyan>Przetwarzanie wydarzenia: {event['name']}</cyan>")
                
                # Zapisz lub znajdź wydarzenie w bazie
                event_id = self._save_or_get_event(event, data_source_id)
                
                if not event_id:
                    self.logger.warning(f"<yellow>Nie udało się zapisać wydarzenia: {event['name']}</yellow>")
                    continue
                
                # Pobierz wystawców dla tego wydarzenia
                exhibitors_url = event.get('exhibitors_url', '')
                if not exhibitors_url:
                    self.logger.debug(f"Brak URL wystawców dla: {event['name']}")
                    continue
                
                # Sprawdź liczbę firm w bazie vs oczekiwana liczba z API
                db_count = self._get_event_company_count(event_id)
                expected_count = self.parser.get_exhibitors_count_fast(exhibitors_url, self.engine)
                
                if expected_count == 0:
                    self.logger.debug(f"Brak wystawców dla: {event['name']}")
                    continue
                
                if db_count >= expected_count:
                    self.logger.info(f"<yellow>Pominięto {event['name']} - już mamy {db_count}/{expected_count} firm</yellow>")
                    skipped_events += 1
                    continue
                
                self.logger.info(f"<cyan>Pobieranie wystawców: {db_count} w bazie, {expected_count} dostępnych</cyan>")
                
                # Pobierz pełną listę wystawców
                exhibitors = self.parser.get_exhibitors(exhibitors_url, self.engine)
                
                # Pobierz istniejące nazwy firm dla tego wydarzenia
                existing_names = self._get_existing_company_names(event_id)
                
                # Zapisz tylko nowe firmy
                saved_count = 0
                for exhibitor in exhibitors:
                    name = exhibitor.get('name', '')
                    if name and name[:250] not in existing_names:
                        if self._save_company(exhibitor, event_id):
                            saved_count += 1
                
                total_exhibitors += saved_count
                processed_events += 1
                
                self.logger.info(f"<green>Dodano {saved_count} nowych wystawców dla: {event['name']}</green>")
                
                # Opóźnienie między wydarzeniami
                self.engine.wait()
                
            except Exception as e:
                self.logger.error(f"<red>Błąd przetwarzania wydarzenia {event.get('name', 'Unknown')}: {e}</red>")
                continue
        
        self.logger.info("<cyan>=</cyan>" * 50)
        self.logger.info(f"<green>Zakończono scrapowanie</green>")
        self.logger.info(f"<green>Przetworzonych wydarzeń: {processed_events}</green>")
        self.logger.info(f"<yellow>Pominiętych (bez zmian): {skipped_events}</yellow>")
        self.logger.info(f"<green>Dodanych wystawców: {total_exhibitors}</green>")
        self.logger.info("<cyan>=</cyan>" * 50)
        
        return True
    
    def _ensure_data_source(self) -> Optional[int]:
        """Upewnia się, że istnieje wpis DataSource dla targikielce.pl"""
        try:
            # Sprawdź czy już istnieje
            result = self.db.execute_query(
                "SELECT Id FROM [Dictionary].[DataSource] WHERE Name = ?",
                ("Targi Kielce",)
            )
            
            if result and len(result) > 0:
                return result[0]['Id']
            
            # Utwórz nowy wpis
            self.db.execute_query(
                """INSERT INTO [Dictionary].[DataSource] (AddDateTime, Name, WWW) 
                   VALUES (GETDATE(), ?, ?)""",
                ("Targi Kielce", "https://www.targikielce.pl"),
                fetch=False
            )
            
            # Pobierz ID nowego wpisu
            result = self.db.execute_query(
                "SELECT Id FROM [Dictionary].[DataSource] WHERE Name = ?",
                ("Targi Kielce",)
            )
            
            if result and len(result) > 0:
                self.logger.info("<green>Utworzono nowe źródło danych: Targi Kielce</green>")
                return result[0]['Id']
            
            return None
            
        except DatabaseError as e:
            self.logger.error(f"<red>Błąd dostępu do DataSource: {e}</red>")
            return None
    
    def _filter_future_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filtruje tylko przyszłe wydarzenia"""
        today = datetime.now().date()
        future_events = []
        
        for event in events:
            try:
                date_str = event.get('date', '')
                if not date_str:
                    future_events.append(event)  # Brak daty = uwzględnij
                    continue
                
                # Parsuj datę (format: DD-DD.MM.YYYY lub DD.MM.YYYY)
                # Weź ostatnią datę jeśli jest zakres
                parts = date_str.replace('-', '.').split('.')
                
                if len(parts) >= 3:
                    # Znajdź rok (4 cyfry)
                    year = None
                    month = None
                    day = None
                    
                    for part in reversed(parts):
                        if len(part) == 4 and part.isdigit():
                            year = int(part)
                        elif len(part) <= 2 and part.isdigit():
                            if month is None:
                                month = int(part)
                            else:
                                day = int(part)
                    
                    if year and month:
                        if day is None:
                            day = 1
                        event_date = datetime(year, month, day).date()
                        
                        if event_date >= today:
                            future_events.append(event)
                else:
                    future_events.append(event)  # Nierozpoznany format = uwzględnij
                    
            except Exception:
                future_events.append(event)  # Błąd parsowania = uwzględnij
        
        return future_events
    
    def _save_or_get_event(self, event: Dict[str, Any], data_source_id: int) -> Optional[int]:
        """Zapisuje wydarzenie do bazy lub zwraca istniejące ID"""
        try:
            name = event.get('name', '')[:50]  # Limit 50 znaków w bazie
            
            # Sprawdź czy wydarzenie już istnieje
            result = self.db.execute_query(
                "SELECT Id FROM [CRM].[Event] WHERE Name = ?",
                (name,)
            )
            
            if result and len(result) > 0:
                return result[0]['Id']
            
            # Parsuj datę wydarzenia
            event_date = self._parse_event_date(event.get('date', ''))
            
            # Utwórz nowe wydarzenie
            self.db.execute_query(
                """INSERT INTO [CRM].[Event] (AddDateTime, Name, EventDate, WWW, DataSourceId)
                   VALUES (GETDATE(), ?, ?, ?, ?)""",
                (name, event_date, event.get('url', '')[:500], data_source_id),
                fetch=False
            )
            
            # Pobierz ID nowego wydarzenia
            result = self.db.execute_query(
                "SELECT Id FROM [CRM].[Event] WHERE Name = ?",
                (name,)
            )
            
            if result and len(result) > 0:
                self.logger.debug(f"Utworzono nowe wydarzenie: {name}")
                return result[0]['Id']
            
            return None
            
        except DatabaseError as e:
            self.logger.error(f"<red>Błąd zapisywania wydarzenia: {e}</red>")
            return None
    
    def _parse_event_date(self, date_str: str) -> str:
        """Parsuje datę wydarzenia do formatu YYYY-MM-DD"""
        try:
            if not date_str:
                return datetime.now().strftime('%Y-%m-%d')
            
            # Format: DD-DD.MM.YYYY lub DD.MM.YYYY
            parts = date_str.replace('-', '.').split('.')
            
            if len(parts) >= 3:
                year = None
                month = None
                day = None
                
                for part in reversed(parts):
                    if len(part) == 4 and part.isdigit():
                        year = int(part)
                    elif len(part) <= 2 and part.isdigit():
                        if month is None:
                            month = int(part)
                        else:
                            day = int(part)
                
                if year and month and day:
                    return f"{year:04d}-{month:02d}-{day:02d}"
            
            return datetime.now().strftime('%Y-%m-%d')
            
        except Exception:
            return datetime.now().strftime('%Y-%m-%d')
    
    def _get_event_company_count(self, event_id: int) -> int:
        """Pobiera liczbę firm zapisanych dla danego wydarzenia"""
        try:
            result = self.db.execute_query(
                "SELECT COUNT(*) as cnt FROM [CRM].[Company] WHERE EventId = ?",
                (event_id,)
            )
            if result and len(result) > 0:
                return result[0]['cnt']
        except DatabaseError:
            pass
        return 0
    
    def _get_existing_company_names(self, event_id: int) -> set:
        """Pobiera zbiór nazw firm dla danego wydarzenia"""
        try:
            result = self.db.execute_query(
                "SELECT Name FROM [CRM].[Company] WHERE EventId = ?",
                (event_id,)
            )
            if result:
                return {row['Name'] for row in result}
        except DatabaseError:
            pass
        return set()
    
    def _save_company(self, exhibitor: Dict[str, Any], event_id: int) -> bool:
        """Zapisuje firmę (wystawcę) do bazy danych"""
        try:
            name = exhibitor.get('name', '')
            if not name:
                return False
            
            # Sprawdź czy firma już istnieje dla tego wydarzenia
            result = self.db.execute_query(
                "SELECT Id FROM [CRM].[Company] WHERE Name = ? AND EventId = ?",
                (name[:250], event_id)
            )
            
            if result and len(result) > 0:
                self.logger.debug(f"Firma już istnieje: {name}")
                return False  # Już istnieje
            
            # Pobierz domyślne wartości z konfiguracji
            default_country_id = self.get_config_value("mapping.default_country_id", 1)
            default_industry_id = self.get_config_value("mapping.default_industry_id", 1)
            
            # Mapowanie kraju (opcjonalne)
            country = exhibitor.get('country', '')
            country_id = self._get_country_id(country) if country else default_country_id
            
            # Link do strony firmy w ramach wydarzenia (details_url)
            company_event_link = exhibitor.get('details_url', '')[:500] if exhibitor.get('details_url') else None
            
            # Zapisz firmę (bez ContactDataSourceId - uzupełnimy gdy pobierzemy dane kontaktowe)
            self.db.execute_query(
                """INSERT INTO [CRM].[Company] 
                   (AddDateTime, EventId, IndustryId, Name, Description, Address, 
                    CountryId, Phone, Email, WWW, CompanyEventLink)
                   VALUES (GETDATE(), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event_id,
                    default_industry_id,
                    name[:250],
                    exhibitor.get('description', '')[:8000] if exhibitor.get('description') else None,
                    exhibitor.get('address', '')[:500] if exhibitor.get('address') else None,
                    country_id,
                    exhibitor.get('phone', '')[:20] if exhibitor.get('phone') else None,
                    exhibitor.get('email', '')[:500] if exhibitor.get('email') else None,
                    exhibitor.get('www', '')[:500] if exhibitor.get('www') else None,
                    company_event_link
                ),
                fetch=False
            )
            
            return True
            
        except DatabaseError as e:
            self.logger.debug(f"Błąd zapisywania firmy {exhibitor.get('name', 'Unknown')}: {e}")
            return False
    
    def _get_country_id(self, country_name: str) -> int:
        """Pobiera ID kraju na podstawie nazwy"""
        default_id = self.get_config_value("mapping.default_country_id", 1)
        
        if not country_name:
            return default_id
        
        try:
            # Sprawdź czy kraj istnieje
            result = self.db.execute_query(
                "SELECT Id FROM [Dictionary].[Country] WHERE Name = ?",
                (country_name[:50],)
            )
            
            if result and len(result) > 0:
                return result[0]['Id']
            
            # Utwórz nowy kraj
            self.db.execute_query(
                "INSERT INTO [Dictionary].[Country] (AddDateTime, Name) VALUES (GETDATE(), ?)",
                (country_name[:50],),
                fetch=False
            )
            
            # Pobierz ID
            result = self.db.execute_query(
                "SELECT Id FROM [Dictionary].[Country] WHERE Name = ?",
                (country_name[:50],)
            )
            
            if result and len(result) > 0:
                return result[0]['Id']
            
            return default_id
            
        except DatabaseError:
            return default_id


def main():
    """Główna funkcja modułu"""
    module = WebsiteScraperModule()
    return module.run()


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
