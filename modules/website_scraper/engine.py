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
        
        # Domyślne nagłówki (nowoczesna przeglądarka)
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate',  # bez brotli - wymaga dodatkowej biblioteki
            'Connection': 'keep-alive',
        })
    
    def fetch_url(self, url: str, method: str = 'GET', **kwargs) -> Optional[requests.Response]:
        """
        Pobiera zawartość strony z obsługą retry i błędów
        
        Args:
            url: URL do pobrania
            method: Metoda HTTP (GET lub POST)
            **kwargs: Dodatkowe parametry dla requests
        
        Returns:
            Response obiekt lub None w przypadku błędu
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                self.logger.debug(f"Pobieranie URL (próba {attempt}/{self.max_retries}): {url}")
                
                if method.upper() == 'POST':
                    response = self.session.post(url, timeout=self.timeout, **kwargs)
                else:
                    response = self.session.get(url, timeout=self.timeout, **kwargs)
                
                response.raise_for_status()
                
                self.logger.debug(f"Pomyślnie pobrano URL: {url} (status: {response.status_code})")
                return response
            
            except requests.exceptions.HTTPError as e:
                # Błędy klienta (4xx) - nie ponawiaj
                if e.response is not None and 400 <= e.response.status_code < 500:
                    self.logger.debug(f"HTTP {e.response.status_code} dla: {url}")
                    return None
                
                self.logger.warning(f"Błąd HTTP (próba {attempt}/{self.max_retries}): {url} - {e}")
                if attempt < self.max_retries:
                    time.sleep(self.delay * attempt)
                else:
                    return None
                    
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
    
    def fetch_json(self, url: str, method: str = 'GET', referer: Optional[str] = None, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Pobiera dane JSON z URL
        
        Args:
            url: URL do pobrania
            method: Metoda HTTP (GET lub POST)
            referer: Nagłówek Referer (niektóre API wymagają)
            **kwargs: Dodatkowe parametry dla requests
        
        Returns:
            Słownik z danymi JSON lub None w przypadku błędu
        """
        # Dodaj nagłówki dla JSON
        headers = kwargs.pop('headers', {})
        headers.update({
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'X-Requested-With': 'XMLHttpRequest',
        })
        
        # Dodaj Referer jeśli podany lub wygeneruj z URL
        if referer:
            headers['Referer'] = referer
        else:
            # Generuj Referer z bazowego URL
            from urllib.parse import urlparse
            parsed = urlparse(url)
            headers['Referer'] = f"{parsed.scheme}://{parsed.netloc}/"
        
        response = self.fetch_url(url, method=method, headers=headers, **kwargs)
        
        if not response:
            return None
        
        try:
            return response.json()
        except Exception as e:
            self.logger.error(f"Błąd parsowania JSON z {url}: {e}")
            self.logger.debug(f"Status: {response.status_code}, Content-Type: {response.headers.get('content-type')}")
            self.logger.debug(f"Response (pierwsze 200 znaków): {response.text[:200] if response.text else 'EMPTY'}")
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
    
    def wait(self, seconds: Optional[float] = None):
        """
        Czeka określony czas (używane do opóźnień między żądaniami)
        
        Args:
            seconds: Czas oczekiwania w sekundach (domyślnie self.delay)
        """
        wait_time = seconds if seconds is not None else self.delay
        if wait_time > 0:
            time.sleep(wait_time)
    
    def close(self):
        """Zamyka sesję HTTP"""
        if self.session:
            self.session.close()
