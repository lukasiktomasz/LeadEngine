"""
Wspólny silnik scrapowania - obsługa HTTP, retry, error handling
"""

import time
import requests
from typing import Optional, Dict, Any
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class ScrapingEngine:
    """Wspólny silnik do scrapowania stron internetowych"""
    
    def __init__(self, logger, max_retries: int = 3, timeout: int = 30, delay: float = 1.0):
        """
        Inicjalizuje silnik scrapowania
        
        Args:
            logger: Logger do logowania
            max_retries: Maksymalna liczba prób ponowienia
            timeout: Timeout żądania w sekundach
            delay: Opóźnienie między próbami w sekundach
        """
        self.logger = logger
        self.max_retries = max_retries
        self.timeout = timeout
        self.delay = delay
        
        # Konfiguracja sesji HTTP z retry
        self.session = requests.Session()
        
        # Strategia retry
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Domyślne nagłówki
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def fetch_url(self, url: str, **kwargs) -> Optional[requests.Response]:
        """
        Pobiera zawartość strony z obsługą retry i błędów
        
        Args:
            url: URL do pobrania
            **kwargs: Dodatkowe parametry dla requests.get()
        
        Returns:
            Response obiekt lub None w przypadku błędu
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                self.logger.debug(f"Pobieranie URL (próba {attempt}/{self.max_retries}): {url}")
                
                response = self.session.get(url, timeout=self.timeout, **kwargs)
                response.raise_for_status()
                
                self.logger.debug(f"Pomyślnie pobrano URL: {url} (status: {response.status_code})")
                return response
            
            except requests.exceptions.RequestException as e:
                self.logger.warning(f"Błąd pobierania URL (próba {attempt}/{self.max_retries}): {url} - {e}")
                
                if attempt < self.max_retries:
                    wait_time = self.delay * attempt
                    self.logger.debug(f"Oczekiwanie {wait_time}s przed ponowną próbą...")
                    time.sleep(wait_time)
                else:
                    self.logger.error(f"Nie udało się pobrać URL po {self.max_retries} próbach: {url}")
                    return None
        
        return None
    
    def get_html_content(self, url: str, encoding: Optional[str] = None) -> Optional[str]:
        """
        Pobiera zawartość HTML strony
        
        Args:
            url: URL do pobrania
            encoding: Kodowanie znaków (jeśli None, wykryje automatycznie)
        
        Returns:
            Zawartość HTML jako string lub None w przypadku błędu
        """
        response = self.fetch_url(url)
        
        if not response:
            return None
        
        try:
            # Ustaw kodowanie jeśli podano
            if encoding:
                response.encoding = encoding
            else:
                # Spróbuj wykryć kodowanie
                if response.encoding is None or response.encoding == 'ISO-8859-1':
                    response.encoding = response.apparent_encoding or 'utf-8'
            
            return response.text
        
        except Exception as e:
            self.logger.error(f"Błąd odczytu zawartości HTML z {url}: {e}")
            return None
    
    def close(self):
        """Zamyka sesję HTTP"""
        if self.session:
            self.session.close()

