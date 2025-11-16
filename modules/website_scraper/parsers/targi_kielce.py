"""
Parser dla strony targikielce.pl
"""

from ..base_parser import BaseParser
from bs4 import BeautifulSoup
from typing import Dict, Any, Optional
import re


class TargiKielceParser(BaseParser):
    """Parser dla strony targikielce.pl"""
    
    def get_parser_name(self) -> str:
        """Zwraca nazwę parsera"""
        return "targi_kielce"
    
    def parse(self, html_content: str, url: str) -> Optional[Dict[str, Any]]:
        """
        Parsuje zawartość HTML strony targikielce.pl
        
        Args:
            html_content: Zawartość HTML
            url: URL strony
        
        Returns:
            Słownik z danymi firmy
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # TODO: Dostosuj selektory do rzeczywistej struktury strony targikielce.pl
            # Poniżej przykładowe selektory - należy je zweryfikować i dostosować
            
            name = self._extract_text(soup, 'h1, .company-name, .firma-nazwa', '')
            address = self._extract_text(soup, '.address, .adres', '')
            phone = self._extract_text(soup, '.phone, .telefon', '')
            email = self._extract_text(soup, '.email, .e-mail', '')
            www = self._extract_attribute(soup, 'a[href*="http"]', 'href', '')
            description = self._extract_text(soup, '.description, .opis', '')
            
            # Alternatywnie można użyć regex do ekstrakcji email i telefonu
            if not email:
                email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', html_content)
                if email_match:
                    email = email_match.group(0)
            
            if not phone:
                phone_match = re.search(r'(\+?\d{1,3}[\s-]?)?\(?\d{2,3}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}', html_content)
                if phone_match:
                    phone = phone_match.group(0)
            
            # Walidacja - przynajmniej nazwa musi być
            if not name:
                self.logger.warning(f"Nie znaleziono nazwy firmy na stronie: {url}")
                return None
            
            return {
                'name': name,
                'address': address,
                'phone': phone,
                'email': email,
                'www': www or url,  # Jeśli nie ma www, użyj URL źródłowego
                'description': description,
            }
        
        except Exception as e:
            self.logger.error(f"Błąd parsowania strony {url}: {e}")
            return None

