"""
Klasa bazowa dla parserów stron źródłowych
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from bs4 import BeautifulSoup


class BaseParser(ABC):
    """Klasa bazowa dla wszystkich parserów stron źródłowych"""
    
    def __init__(self, logger):
        """
        Inicjalizuje parser
        
        Args:
            logger: Logger do logowania
        """
        self.logger = logger
    
    @abstractmethod
    def parse(self, html_content: str, url: str) -> Optional[Dict[str, Any]]:
        """
        Parsuje zawartość HTML i zwraca dane firmy
        
        Args:
            html_content: Zawartość HTML strony
            url: URL strony źródłowej
        
        Returns:
            Słownik z danymi firmy lub None jeśli nie udało się sparsować
            Format: {
                'name': str,
                'address': str,
                'phone': str,
                'email': str,
                'www': str,
                'description': str,
                ...
            }
        """
        pass
    
    @abstractmethod
    def get_parser_name(self) -> str:
        """
        Zwraca nazwę parsera (używana do identyfikacji)
        
        Returns:
            Nazwa parsera
        """
        pass
    
    def _clean_text(self, text: Optional[str]) -> Optional[str]:
        """
        Czyści tekst z białych znaków i znaków specjalnych
        
        Args:
            text: Tekst do wyczyszczenia
        
        Returns:
            Wyczyszczony tekst lub None
        """
        if not text:
            return None
        
        # Usuń białe znaki z początku i końca
        cleaned = text.strip()
        
        # Usuń wielokrotne spacje
        cleaned = ' '.join(cleaned.split())
        
        return cleaned if cleaned else None
    
    def _extract_text(self, soup: BeautifulSoup, selector: str, default: Optional[str] = None) -> Optional[str]:
        """
        Ekstrahuje tekst z elementu HTML używając selektora CSS
        
        Args:
            soup: BeautifulSoup obiekt
            selector: Selektor CSS
            default: Wartość domyślna jeśli element nie zostanie znaleziony
        
        Returns:
            Tekst z elementu lub wartość domyślna
        """
        try:
            element = soup.select_one(selector)
            if element:
                return self._clean_text(element.get_text())
        except Exception as e:
            self.logger.debug(f"Błąd ekstrakcji tekstu z selektora '{selector}': {e}")
        
        return default
    
    def _extract_attribute(self, soup: BeautifulSoup, selector: str, attribute: str, default: Optional[str] = None) -> Optional[str]:
        """
        Ekstrahuje wartość atrybutu z elementu HTML
        
        Args:
            soup: BeautifulSoup obiekt
            selector: Selektor CSS
            attribute: Nazwa atrybutu (np. 'href', 'src')
            default: Wartość domyślna
        
        Returns:
            Wartość atrybutu lub wartość domyślna
        """
        try:
            element = soup.select_one(selector)
            if element and element.has_attr(attribute):
                return self._clean_text(element[attribute])
        except Exception as e:
            self.logger.debug(f"Błąd ekstrakcji atrybutu '{attribute}' z selektora '{selector}': {e}")
        
        return default

