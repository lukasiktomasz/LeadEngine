"""
Moduł logowania z rotacją plików i obsługą konsoli z kolorami
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

try:
    from colorama import init, Fore, Style
    init(autoreset=True)  # Automatycznie resetuj kolory po każdym print
    COLORAMA_AVAILABLE = True
except ImportError:
    COLORAMA_AVAILABLE = False
    # Fallback - kody ANSI dla systemów które je obsługują
    class Fore:
        BLACK = '\033[30m'
        RED = '\033[31m'
        GREEN = '\033[32m'
        YELLOW = '\033[33m'
        BLUE = '\033[34m'
        MAGENTA = '\033[35m'
        CYAN = '\033[36m'
        WHITE = '\033[37m'
        RESET = '\033[0m'
    
    class Style:
        RESET_ALL = '\033[0m'
        BRIGHT = '\033[1m'


def setup_logger(
    name: str = "LeadEngine",
    log_dir: str = "logs",
    log_file: str = "app.log",
    level: int = logging.INFO,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> logging.Logger:
    """
    Konfiguruje i zwraca logger z rotacją plików
    
    Args:
        name: Nazwa loggera
        log_dir: Katalog na pliki logów
        log_file: Nazwa pliku logów
        level: Poziom logowania (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        max_bytes: Maksymalny rozmiar pliku przed rotacją
        backup_count: Liczba plików backup do przechowania
    
    Returns:
        Logger skonfigurowany z obsługą pliku i konsoli
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Unikaj duplikowania handlerów
    if logger.handlers:
        return logger
    
    # Utwórz katalog na logi jeśli nie istnieje
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)
    
    # Format logów (bez kolorów dla pliku)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Format logów z kolorami dla konsoli
    class ColoredFormatter(logging.Formatter):
        """Formatter z kolorami dla różnych poziomów logowania"""
        
        # Mapowanie poziomów na kolory
        COLORS = {
            'DEBUG': Fore.CYAN,
            'INFO': Fore.GREEN,
            'WARNING': Fore.YELLOW,
            'ERROR': Fore.RED,
            'CRITICAL': Fore.RED + Style.BRIGHT,
        }
        
        def _parse_color_tags(self, text):
            """Parsuje tagi kolorów w stylu <color>tekst</color> i zamienia na kody kolorów"""
            import re
            
            # Mapowanie nazw kolorów na kody
            color_map = {
                'black': Fore.BLACK if COLORAMA_AVAILABLE else '\033[30m',
                'red': Fore.RED if COLORAMA_AVAILABLE else '\033[31m',
                'green': Fore.GREEN if COLORAMA_AVAILABLE else '\033[32m',
                'yellow': Fore.YELLOW if COLORAMA_AVAILABLE else '\033[33m',
                'blue': Fore.BLUE if COLORAMA_AVAILABLE else '\033[34m',
                'magenta': Fore.MAGENTA if COLORAMA_AVAILABLE else '\033[35m',
                'cyan': Fore.CYAN if COLORAMA_AVAILABLE else '\033[36m',
                'white': Fore.WHITE if COLORAMA_AVAILABLE else '\033[37m',
                'lightblue': Fore.LIGHTBLUE_EX if COLORAMA_AVAILABLE and hasattr(Fore, 'LIGHTBLUE_EX') else '\033[94m',
            }
            reset_color = Style.RESET_ALL if COLORAMA_AVAILABLE else '\033[0m'
            
            # Wzorzec: <color>tekst</color>
            pattern = r'<(\w+)>(.*?)</\1>'
            
            def replace_tag(match):
                color_name = match.group(1).lower()
                text_content = match.group(2)
                color_code = color_map.get(color_name, '')
                if color_code:
                    return f"{color_code}{text_content}{reset_color}"
                return match.group(0)  # Jeśli kolor nieznany, zwróć oryginał
            
            return re.sub(pattern, replace_tag, text)
        
        def format(self, record):
            # Zapisz oryginalne wartości
            original_levelname = record.levelname
            original_name = record.name
            original_asctime = getattr(record, 'asctime', None)
            original_msg = record.msg
            
            # Parsuj tagi kolorów w wiadomości
            if isinstance(record.msg, str):
                record.msg = self._parse_color_tags(record.msg)
            
            # Pobierz kolor dla danego poziomu
            log_color = self.COLORS.get(record.levelname, '')
            reset_color = Style.RESET_ALL if COLORAMA_AVAILABLE else '\033[0m'
            
            # Dodaj kolory do elementów
            record.levelname = f"{log_color}{record.levelname}{reset_color}"
            
            # Kolor dla nazwy loggera (jasny niebieski)
            if COLORAMA_AVAILABLE:
                name_color = Fore.LIGHTBLUE_EX if hasattr(Fore, 'LIGHTBLUE_EX') else Fore.CYAN
            else:
                name_color = '\033[94m'  # Jasny niebieski w ANSI
            record.name = f"{name_color}{record.name}{reset_color}"
            
            # Formatuj wiadomość (to utworzy asctime jeśli nie istnieje)
            formatted = super().format(record)
            
            # Dodaj kolor do timestamp (jeśli istnieje)
            if hasattr(record, 'asctime') and record.asctime:
                time_color = Fore.CYAN if COLORAMA_AVAILABLE else '\033[36m'
                # Zastąp timestamp w sformatowanym stringu
                formatted = formatted.replace(record.asctime, f"{time_color}{record.asctime}{reset_color}", 1)
            
            # Przywróć oryginalne wartości (dla innych handlerów)
            record.levelname = original_levelname
            record.name = original_name
            record.msg = original_msg
            if original_asctime is not None:
                record.asctime = original_asctime
            elif hasattr(record, 'asctime'):
                delattr(record, 'asctime')
            
            return formatted
    
    console_formatter = ColoredFormatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Handler do pliku z rotacją (bez kolorów)
    file_handler = RotatingFileHandler(
        log_path / log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(file_formatter)
    
    # Handler do konsoli (z kolorami)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(console_formatter)
    
    # Dodaj handlery do loggera
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

