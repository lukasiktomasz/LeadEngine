"""
Główny plik modułu website_scraper
Punkt wejścia do uruchomienia modułu
"""

import sys
import logging
from pathlib import Path
from typing import Optional

# Dodaj katalog główny projektu do ścieżki
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from common.base_module import BaseModule
from common.database import DatabaseError
from .engine import ScrapingEngine
from .base_parser import BaseParser
from .parsers.targi_kielce import TargiKielceParser
from .parsers.example_site import ExampleSiteParser


def get_parser_for_url(url: str, module_config: dict, logger) -> BaseParser:
    """
    Zwraca odpowiedni parser dla danego URL
    
    Args:
        url: URL strony
        config: Konfiguracja modułu
        logger: Logger
    
    Returns:
        Instancja parsera
    """
    from common.config import get_config_value
    parser_mapping = get_config_value(module_config, "database.parser_mapping", {})
    
    # Sprawdź mapowanie parserów
    for domain, parser_name in parser_mapping.items():
        if domain in url.lower():
            if parser_name == "targi_kielce":
                return TargiKielceParser(logger)
            elif parser_name == "example_site":
                return ExampleSiteParser(logger)
    
    # Domyślnie użyj parsera targi_kielce
    logger.warning(f"Nie znaleziono mapowania parsera dla URL: {url}, używam domyślnego")
    return TargiKielceParser(logger)


def save_company_to_db(db, company_data: dict, module_config: dict, source_event_id: int = None) -> bool:
    """
    Zapisuje dane firmy do bazy danych
    
    Args:
        db: Połączenie z bazą danych
        company_data: Dane firmy do zapisania
        config: Konfiguracja modułu
        source_event_id: ID wydarzenia źródłowego (opcjonalne)
    
    Returns:
        True jeśli zapisano pomyślnie, False w przeciwnym razie
    """
    try:
        from common.config import get_config_value
        # Pobierz wartości domyślne z konfiguracji
        default_country_id = get_config_value(module_config, "mapping.default_country_id", 1)
        default_industry_id = get_config_value(module_config, "mapping.default_industry_id", 1)
        default_data_source_id = get_config_value(module_config, "mapping.default_contact_data_source_id", 1)
        
        # Przygotuj zapytanie INSERT
        query = """
            INSERT INTO [CRM].[Company] 
            (AddDateTime, EventId, IndustryId, Name, Description, Address, CountryId, Phone, Email, WWW, ContactDataSourceId)
            VALUES (GETDATE(), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        params = (
            source_event_id if source_event_id else None,
            default_industry_id,
            company_data.get('name', ''),
            company_data.get('description'),
            company_data.get('address'),
            default_country_id,
            company_data.get('phone'),
            company_data.get('email'),
            company_data.get('www'),
            default_data_source_id
        )
        
        db.execute_query(query, params, fetch=False)
        return True
    
    except Exception as e:
        raise DatabaseError(f"Błąd zapisywania firmy do bazy danych: {e}")


class WebsiteScraperModule(BaseModule):
    """Moduł do pobierania danych firm z witryn internetowych"""
    
    def __init__(self):
        super().__init__(
            module_name="WebsiteScraper",
            module_config_path="modules/website_scraper/config.json",
            log_file="website_scraper.log"
        )
        self.engine: Optional[ScrapingEngine] = None
    
    def _init_module(self) -> bool:
        """Inicjalizacja silnika scrapowania"""
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
            return True
        except Exception as e:
            self.logger.error(f"<red>Błąd inicjalizacji silnika scrapowania: {e}</red>")
            return False
    
    def _cleanup_module(self) -> None:
        """Zamykanie silnika scrapowania"""
        if self.engine:
            self.engine.close()
    
    def execute(self) -> bool:
        """Główna logika scrapowania"""
        # Odczytywanie listy URL-i z bazy danych
        self.logger.info("<yellow>Odczytywanie listy URL-i z bazy danych...</yellow>")
        
        source_table = self.get_config_value("database.source_table", "CRM.Event")
        source_url_column = self.get_config_value("database.source_url_column", "WWW")
        source_id_column = self.get_config_value("database.source_id_column", "Id")
        
        query = f"""
            SELECT TOP 10 {source_id_column}, {source_url_column}
            FROM {source_table}
            WHERE {source_url_column} IS NOT NULL AND {source_url_column} != ''
        """
        
        try:
            urls = self.db.execute_query(query)
            self.logger.info(f"<green>Znaleziono {len(urls) if urls else 0} URL-i do przetworzenia</green>")
        except DatabaseError as e:
            self.logger.error(f"<red>Błąd odczytu URL-i z bazy danych: {e}</red>")
            return False
        
        if not urls:
            self.logger.warning("<yellow>Brak URL-i do przetworzenia</yellow>")
            return True
        
        # Przetwarzanie każdego URL-a
        self.logger.info("<yellow>Rozpoczynanie scrapowania...</yellow>")
        
        for url_record in urls:
            url = url_record.get(source_url_column)
            event_id = url_record.get(source_id_column)
            
            if not url:
                continue
            
            self.logger.info(f"<cyan>Przetwarzanie: {url}</cyan>")
            
            # Pobierz zawartość strony
            html_content = self.engine.get_html_content(url)
            
            if not html_content:
                self.logger.warning(f"<yellow>Nie udało się pobrać zawartości: {url}</yellow>")
                continue
            
            # Wybierz odpowiedni parser
            parser = get_parser_for_url(url, self.module_config, self.logger)
            
            # Parsuj zawartość
            company_data = parser.parse(html_content, url)
            
            if not company_data:
                self.logger.warning(f"<yellow>Nie udało się sparsować danych z: {url}</yellow>")
                continue
            
            # Zapisz do bazy danych
            try:
                save_company_to_db(self.db, company_data, self.module_config, source_event_id=event_id)
                self.logger.info(f"<green>Zapisano firmę: {company_data.get('name', 'N/A')}</green>")
            except DatabaseError as e:
                self.logger.error(f"<red>Błąd zapisywania firmy: {e}</red>")
        
        self.logger.info("<green>Scrapowanie zakończone pomyślnie</green>")
        return True


def main():
    """Główna funkcja modułu"""
    module = WebsiteScraperModule()
    return module.run()


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

