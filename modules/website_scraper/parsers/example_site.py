"""
Przykładowy parser - szablon do tworzenia nowych parserów
"""

from ..base_parser import BaseParser
from bs4 import BeautifulSoup
from typing import Dict, Any, Optional


class ExampleSiteParser(BaseParser):
    """Przykładowy parser - szablon"""
    
    def get_parser_name(self) -> str:
        """Zwraca nazwę parsera"""
        return "example_site"
    
    def parse(self, html_content: str, url: str) -> Optional[Dict[str, Any]]:
        """
        Parsuje zawartość HTML strony przykład.com
        
        Args:
            html_content: Zawartość HTML
            url: URL strony
        
        Returns:
            Słownik z danymi firmy
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Przykładowa ekstrakcja danych - dostosuj selektory do konkretnej strony
            name = self._extract_text(soup, 'h1.company-name', '')
            address = self._extract_text(soup, '.company-address', '')
            phone = self._extract_text(soup, '.company-phone', '')
            email = self._extract_text(soup, '.company-email', '')
            www = self._extract_attribute(soup, 'a.company-website', 'href', '')
            description = self._extract_text(soup, '.company-description', '')
            
            # Walidacja - przynajmniej nazwa musi być
            if not name:
                self.logger.warning(f"Nie znaleziono nazwy firmy na stronie: {url}")
                return None
            
            return {
                'name': name,
                'address': address,
                'phone': phone,
                'email': email,
                'www': www,
                'description': description,
            }
        
        except Exception as e:
            self.logger.error(f"Błąd parsowania strony {url}: {e}")
            return None

