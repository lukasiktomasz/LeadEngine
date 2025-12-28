"""
Parser dla strony targikielce.pl
Pobiera listę wydarzeń (targów) i wystawców z Targów Kielce
"""

import re
import json
import time
from typing import Dict, Any, Optional, List
from bs4 import BeautifulSoup

# Import zależny od sposobu uruchomienia
try:
    from ..base_parser import BaseParser
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from base_parser import BaseParser


class TargiKielceParser(BaseParser):
    """Parser dla strony targikielce.pl"""
    
    BASE_URL = "https://www.targikielce.pl"
    TRADES_API_URL = f"{BASE_URL}/api/modules/trades/search/1/60"
    
    def get_parser_name(self) -> str:
        """Zwraca nazwę parsera"""
        return "targi_kielce"
    
    def get_events(self, engine) -> List[Dict[str, Any]]:
        """
        Pobiera listę wydarzeń (targów) z API
        
        Args:
            engine: ScrapingEngine do wykonywania zapytań HTTP
        
        Returns:
            Lista słowników z danymi wydarzeń
        """
        events = []
        
        try:
            self.logger.info("<cyan>Pobieranie listy wydarzeń z targikielce.pl...</cyan>")
            
            response = engine.fetch_json(self.TRADES_API_URL)
            if not response:
                self.logger.error("<red>Nie udało się pobrać listy wydarzeń</red>")
                return events
            
            html_content = response.get('view', '')
            if not html_content:
                self.logger.warning("<yellow>Odpowiedź API nie zawiera pola 'view'</yellow>")
                return events
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            for item in soup.select('a.trades-list-item'):
                event_url = item.get('href', '')
                
                # Pomijamy zewnętrzne linki
                if event_url and 'targikielce.pl' not in event_url and event_url.startswith('http'):
                    continue
                
                event = {
                    'url': event_url,
                    'name': self._extract_text(item, 'h3.trades-list-item__title', ''),
                    'date': self._clean_date(self._extract_text(item, '.trades-list-item__date', '')),
                    'description': self._extract_text(item, '.trades-list-item__description', ''),
                }
                
                # Generuj URL do listy wystawców
                if event['url']:
                    # Zamień "/o-wydarzeniu" na "/lista-wystawcow"
                    if '/o-wydarzeniu' in event['url']:
                        event['exhibitors_url'] = event['url'].replace('/o-wydarzeniu', '/lista-wystawcow')
                    else:
                        # Jeśli nie ma "/o-wydarzeniu", dodaj "/lista-wystawcow" na końcu
                        event['exhibitors_url'] = event['url'].rstrip('/') + '/lista-wystawcow'
                    
                    # Wyodrębnij slug wydarzenia (np. "dachforum")
                    match = re.search(r'targikielce\.pl/([^/]+)', event['url'])
                    if match:
                        event['slug'] = match.group(1)
                
                if event['name']:
                    events.append(event)
                    self.logger.debug(f"Znaleziono wydarzenie: {event['name']} ({event['date']})")
            
            self.logger.info(f"<green>Znaleziono {len(events)} wydarzeń</green>")
            
        except Exception as e:
            self.logger.error(f"<red>Błąd pobierania listy wydarzeń: {e}</red>")
        
        return events
    
    def get_exhibitors_count_fast(self, exhibitors_url: str, engine) -> int:
        """
        Szybkie sprawdzenie liczby wystawców bez pobierania wszystkich danych
        Używa cache z get_exhibitors jeśli dostępny
        
        Args:
            exhibitors_url: URL strony z listą wystawców
            engine: ScrapingEngine do wykonywania zapytań HTTP
        
        Returns:
            Liczba wystawców lub 0 jeśli brak/błąd
        """
        try:
            html_content = engine.get_html_content(exhibitors_url)
            if not html_content:
                return 0
            
            # Cache HTML dla późniejszego użycia przez get_exhibitors
            self._cached_html = html_content
            self._cached_url = exhibitors_url
            
            soup = BeautifulSoup(html_content, 'html.parser')
            api_url, vue_settings = self._extract_exhibitors_api_url(soup)
            
            if vue_settings:
                pager = vue_settings.get('pager', {})
                return pager.get('rowCount', 0)
            
            # Fallback - policz wystawców z HTML
            rows = soup.select('table tr')
            count = len([r for r in rows if r.select_one('div.main-title a')])
            return count
            
        except Exception:
            return 0
    
    def get_exhibitors(self, exhibitors_url: str, engine) -> List[Dict[str, Any]]:
        """
        Pobiera listę wystawców ze strony wydarzenia
        
        Args:
            exhibitors_url: URL strony z listą wystawców
            engine: ScrapingEngine do wykonywania zapytań HTTP
        
        Returns:
            Lista słowników z danymi wystawców
        """
        exhibitors = []
        
        try:
            self.logger.info(f"<cyan>Pobieranie wystawców z: {exhibitors_url}</cyan>")
            
            # Użyj cache z get_exhibitors_count_fast jeśli dostępny
            if hasattr(self, '_cached_html') and hasattr(self, '_cached_url') and self._cached_url == exhibitors_url:
                html_content = self._cached_html
                self._cached_html = None  # Wyczyść cache
                self._cached_url = None
                self.logger.debug("Używam cache HTML z get_exhibitors_count_fast")
            else:
                # Pobierz stronę HTML
                html_content = engine.get_html_content(exhibitors_url)
            
            if not html_content:
                self.logger.warning(f"<yellow>Nie udało się pobrać strony: {exhibitors_url}</yellow>")
                return exhibitors
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Szukaj konfiguracji Vue.js z API URL i ustawieniami pagera
            api_url, vue_settings = self._extract_exhibitors_api_url(soup)
            
            # Szybkie sprawdzenie - jeśli rowCount = 0, nie ma wystawców
            if vue_settings:
                pager = vue_settings.get('pager', {})
                row_count = pager.get('rowCount', 0)
                if row_count == 0:
                    self.logger.debug(f"Brak wystawców (rowCount=0) dla: {exhibitors_url}")
                    return exhibitors
            
            if api_url:
                # Pobierz dane z API wystawców (z pełną paginacją)
                exhibitors = self._fetch_exhibitors_from_api(api_url, engine, vue_settings)
            
            # Jeśli API nie zadziałało, spróbuj z HTML
            if not exhibitors:
                exhibitors = self._parse_exhibitors_from_html(soup)
            
            self.logger.info(f"<green>Znaleziono {len(exhibitors)} wystawców</green>")
            
        except Exception as e:
            self.logger.error(f"<red>Błąd pobierania wystawców z {exhibitors_url}: {e}</red>")
        
        return exhibitors
    
    def _extract_exhibitors_api_url(self, soup: BeautifulSoup) -> tuple:
        """
        Wyodrębnia URL API wystawców i ustawienia z konfiguracji Vue.js
        
        Returns:
            tuple: (api_url, settings_dict) lub (None, None)
        """
        try:
            vue_app = soup.select_one('[data-vue-app="exhibitors-list"]')
            if vue_app:
                settings_raw = vue_app.get('v-init:settings', '')
                if settings_raw:
                    # Dekoduj HTML entities
                    settings_raw = settings_raw.replace('&quot;', '"')
                    settings_data = json.loads(settings_raw)
                    search_url = settings_data.get('searchUrl', '')
                    
                    if search_url:
                        pager = settings_data.get('pager', {})
                        self.logger.debug(f"Znaleziono API wystawców: {search_url}")
                        self.logger.debug(f"Pager: {pager.get('total', '?')} stron, {pager.get('rowCount', '?')} wystawców")
                        return search_url, settings_data
        except json.JSONDecodeError as e:
            self.logger.debug(f"Błąd parsowania JSON z ustawień Vue.js: {e}")
        except Exception as e:
            self.logger.debug(f"Błąd wyodrębniania API URL: {e}")
        
        return None, None
    
    def _parse_exhibitors_from_api_html(self, html: str) -> List[Dict[str, Any]]:
        """
        Parsuje wystawców z HTML zwróconego przez API
        Struktura: <tr><td></td><td><div class="main-title"><a>Nazwa</a></div></td><td>Kraj</td><td>Stoisko</td>...</tr>
        """
        exhibitors = []
        soup = BeautifulSoup(html, 'html.parser')
        
        # API zwraca <tr> bezpośrednio (nie w tbody)
        for row in soup.select('tr'):
            cells = row.select('td')
            if len(cells) < 2:
                continue
            
            # Szukaj nazwy w div.main-title a
            name_link = row.select_one('div.main-title a[href*="lista-wystawcow"]')
            if not name_link:
                # Fallback: szukaj dowolnego linka z lista-wystawcow
                name_link = row.select_one('a[href*="lista-wystawcow"]')
            
            if not name_link:
                continue
            
            name = name_link.get_text(strip=True)
            if not name:
                continue
            
            # URL szczegółów
            href = name_link.get('href', '')
            if href and not href.startswith('http'):
                href = self.BASE_URL + href
            
            # Znajdź indeks komórki z nazwą
            name_cell_idx = -1
            for idx, cell in enumerate(cells):
                if cell.select_one('div.main-title') or name_link in cell.descendants:
                    name_cell_idx = idx
                    break
            
            # Kraj i stoisko są w następnych komórkach
            country = ''
            stand = ''
            
            if name_cell_idx >= 0:
                if len(cells) > name_cell_idx + 1:
                    country = cells[name_cell_idx + 1].get_text(strip=True)
                if len(cells) > name_cell_idx + 2:
                    stand = cells[name_cell_idx + 2].get_text(strip=True)
            
            exhibitor = {
                'name': name,
                'country': country,
                'stand': stand,
                'details_url': href,
            }
            
            # Logo
            logo = row.select_one('img[src], img[data-src]')
            if logo:
                exhibitor['logo_url'] = logo.get('data-src') or logo.get('src', '')
            
            exhibitors.append(exhibitor)
        
        return exhibitors
    
    def _fetch_exhibitors_from_api(self, api_url: str, engine, vue_settings: Dict = None) -> List[Dict[str, Any]]:
        """
        Pobiera wszystkich wystawców z API (obsługuje paginację przez pageIndex)
        
        Format URL: /api/modules/exhibitors-list/search/{page_id}/{trade_id}/{lang}
        Paginacja: ?filters[...]&pageIndex=X&sort[field]=title&sort[method]=asc&count=Y
        """
        all_exhibitors = []
        
        try:
            # Pobierz info o pagerze z ustawień Vue.js (jeśli dostępne)
            pager = {}
            if vue_settings:
                pager = vue_settings.get('pager', {})
            
            total_pages = pager.get('total', 10)  # Domyślnie max 10 stron
            row_count = pager.get('rowCount', 250)  # Domyślnie max 250
            
            self.logger.debug(f"Pager: {total_pages} stron, {row_count} wystawców")
            
            page_index = 1
            max_pages = min(total_pages, 20)  # Limit bezpieczeństwa
            
            while page_index <= max_pages:
                # Pełne parametry jak w przeglądarce
                params = (
                    f"?filters[show_represented_by]=false"
                    f"&filters[query]="
                    f"&filters[alpha]="
                    f"&filters[country]="
                    f"&industryId=0"
                    f"&pageIndex={page_index}"
                    f"&sort[field]=title"
                    f"&sort[method]=asc"
                    f"&count={row_count}"
                )
                current_url = f"{api_url}{params}"
                
                self.logger.debug(f"Pobieranie strony {page_index}/{max_pages}...")
                
                response = engine.fetch_json(current_url)
                if not response:
                    self.logger.debug(f"Brak odpowiedzi dla strony {page_index}")
                    break
                
                # Aktualizuj total_pages z odpowiedzi API (jeśli dostępne)
                settings = response.get('settings', {})
                resp_pager = settings.get('pager', {})
                if resp_pager.get('total'):
                    max_pages = min(resp_pager['total'], 20)
                
                html_content = response.get('view', '')
                if not html_content:
                    self.logger.debug(f"Pusta odpowiedź dla strony {page_index}")
                    break
                
                # Parsuj wystawców z tej strony
                page_exhibitors = self._parse_exhibitors_from_api_html(html_content)
                
                if not page_exhibitors:
                    self.logger.debug(f"Brak wystawców na stronie {page_index} - koniec")
                    break
                
                self.logger.debug(f"Strona {page_index}: {len(page_exhibitors)} wystawców")
                all_exhibitors.extend(page_exhibitors)
                
                # Sprawdź czy to ostatnia strona
                if page_index >= max_pages:
                    break
                
                page_index += 1
                time.sleep(0.3)  # Opóźnienie między stronami
            
            self.logger.info(f"<cyan>Pobrano {len(all_exhibitors)} wystawców z {page_index} stron</cyan>")
                
        except Exception as e:
            self.logger.error(f"<red>Błąd pobierania z API wystawców: {e}</red>")
        
        return all_exhibitors
    
    def _parse_exhibitors_from_html(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Parsuje wystawców z HTML"""
        exhibitors = []
        
        # Metoda 1: Szukaj w tabelach (typowa struktura dla list wystawców targikielce.pl)
        # Struktura: | (puste/logo) | Nazwa | Państwo | Stoisko | ... |
        for row in soup.select('tbody tr'):
            cells = row.select('td')
            if len(cells) < 2:
                continue
            
            # Znajdź komórkę z nazwą firmy (ta która ma link <a>)
            name = ''
            details_url = ''
            name_cell_idx = -1
            
            for idx, cell in enumerate(cells):
                link = cell.select_one('a[href*="lista-wystawcow"]')
                if link:
                    name = link.get_text(strip=True)
                    href = link.get('href', '')
                    if href:
                        if not href.startswith('http'):
                            href = self.BASE_URL + href
                        details_url = href
                    name_cell_idx = idx
                    break
            
            # Jeśli nie znaleziono linku, spróbuj pierwszej niepustej komórki
            if not name:
                for idx, cell in enumerate(cells):
                    text = cell.get_text(strip=True)
                    if text and len(text) > 2:
                        name = text
                        name_cell_idx = idx
                        break
            
            if not name:
                continue
            
            # Określ pozycję kolumn względem nazwy
            # Typowo: nazwa w kolumnie 1, kraj w 2, stoisko w 3
            country = ''
            stand = ''
            
            if name_cell_idx >= 0:
                # Kraj jest zazwyczaj po nazwie
                if len(cells) > name_cell_idx + 1:
                    country = cells[name_cell_idx + 1].get_text(strip=True)
                # Stoisko jest po kraju
                if len(cells) > name_cell_idx + 2:
                    stand = cells[name_cell_idx + 2].get_text(strip=True)
            
            exhibitor = {
                'name': name,
                'country': country,
                'stand': stand,
                'details_url': details_url,
            }
            
            # Logo wystawcy
            logo = row.select_one('img[src], img[data-src]')
            if logo:
                exhibitor['logo_url'] = logo.get('data-src') or logo.get('src', '')
            
            exhibitors.append(exhibitor)
        
        # Metoda 2: Szukaj w innych strukturach (np. div, cards)
        if not exhibitors:
            for item in soup.select('.exhibitor-item, .wystawca, .company-item'):
                name = self._extract_text(item, '.name, .title, h3, h4', '')
                if not name:
                    continue
                
                exhibitor = {
                    'name': name,
                    'country': self._extract_text(item, '.country, .kraj', ''),
                    'stand': self._extract_text(item, '.stand, .stoisko', ''),
                }
                
                link = item.select_one('a[href]')
                if link:
                    href = link.get('href', '')
                    if href and not href.startswith('http'):
                        href = self.BASE_URL + href
                    exhibitor['details_url'] = href
                
                exhibitors.append(exhibitor)
        
        return exhibitors
    
    def get_exhibitor_details(self, details_url: str, engine) -> Optional[Dict[str, Any]]:
        """
        Pobiera szczegółowe dane wystawcy z jego strony
        
        Args:
            details_url: URL strony szczegółów wystawcy
            engine: ScrapingEngine do wykonywania zapytań HTTP
        
        Returns:
            Słownik z danymi firmy lub None
        """
        try:
            html_content = engine.get_html_content(details_url)
            if not html_content:
                return None
            
            return self.parse(html_content, details_url)
            
        except Exception as e:
            self.logger.error(f"<red>Błąd pobierania szczegółów wystawcy: {e}</red>")
            return None
    
    def parse(self, html_content: str, url: str) -> Optional[Dict[str, Any]]:
        """
        Parsuje zawartość HTML strony wystawcy i zwraca dane firmy
        
        Args:
            html_content: Zawartość HTML strony
            url: URL strony źródłowej
        
        Returns:
            Słownik z danymi firmy lub None
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Próbuj różne selektory dla nazwy
            name = (
                self._extract_text(soup, 'h1.company-name', '') or
                self._extract_text(soup, '.exhibitor-name', '') or
                self._extract_text(soup, 'h1', '') or
                self._extract_text(soup, '.page-header h1', '')
            )
            
            if not name:
                self.logger.debug(f"Nie znaleziono nazwy firmy na stronie: {url}")
                return None
            
            # Pobierz pozostałe dane
            address = (
                self._extract_text(soup, '.address', '') or
                self._extract_text(soup, '.company-address', '') or
                self._extract_text(soup, '[itemprop="address"]', '')
            )
            
            description = (
                self._extract_text(soup, '.description', '') or
                self._extract_text(soup, '.company-description', '') or
                self._extract_text(soup, '.about', '')
            )
            
            # Znajdź email i telefon w tekście
            email = self._find_email(html_content)
            phone = self._find_phone(html_content)
            
            # Znajdź link do strony WWW firmy
            www = self._find_website(soup, html_content)
            
            return {
                'name': name,
                'address': address,
                'phone': phone,
                'email': email,
                'www': www or url,
                'description': description,
            }
            
        except Exception as e:
            self.logger.error(f"<red>Błąd parsowania strony {url}: {e}</red>")
            return None
    
    def _clean_date(self, date_str: str) -> str:
        """Czyści i normalizuje format daty"""
        if not date_str:
            return ''
        # Usuń białe znaki i znaki nowej linii
        return ' '.join(date_str.split()).strip()
    
    def _find_email(self, text: str) -> str:
        """Znajduje adres email w tekście"""
        # Pomijaj typowe adresy "no-reply" i systemowe
        excluded_patterns = ['noreply', 'no-reply', 'admin@', 'webmaster@', 'info@targikielce']
        
        matches = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', text)
        for match in matches:
            if not any(excl in match.lower() for excl in excluded_patterns):
                return match
        return ''
    
    def _find_phone(self, text: str) -> str:
        """Znajduje numer telefonu w tekście"""
        # Polski format telefonu
        patterns = [
            r'\+48[\s-]?\d{3}[\s-]?\d{3}[\s-]?\d{3}',  # +48 123 456 789
            r'\d{3}[\s-]?\d{3}[\s-]?\d{3}',  # 123 456 789
            r'\(\d{2,3}\)[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}',  # (12) 345 67 89
            r'\d{2}[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}',  # 12 345 67 89
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        return ''
    
    def _find_website(self, soup: BeautifulSoup, html_content: str) -> str:
        """Znajduje stronę WWW firmy"""
        # Szukaj w elementach HTML
        for selector in ['.website a', '.www a', 'a[href*="http"]']:
            element = soup.select_one(selector)
            if element:
                href = element.get('href', '')
                # Pomijaj linki do targikielce.pl i social media
                if href and 'targikielce.pl' not in href:
                    if not any(x in href for x in ['facebook', 'twitter', 'linkedin', 'instagram', 'youtube']):
                        return href
        
        # Szukaj w tekście
        url_pattern = r'https?://(?:www\.)?([a-zA-Z0-9-]+(?:\.[a-zA-Z]{2,})+)'
        matches = re.findall(url_pattern, html_content)
        for match in matches:
            if 'targikielce' not in match:
                return f"https://www.{match}"
        
        return ''
