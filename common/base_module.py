"""
Klasa bazowa dla wszystkich modułów funkcjonalnych
Zawiera wspólną logikę inicjalizacji, obsługi błędów i zamykania zasobów
"""

import sys
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod

from .logger import setup_logger
from .database import DatabaseConnection, DatabaseError
from .config import load_config, get_config_value, ConfigError


class BaseModule(ABC):
    """Klasa bazowa dla wszystkich modułów funkcjonalnych"""
    
    def __init__(
        self,
        module_name: str,
        module_config_path: Optional[str] = None,
        log_file: Optional[str] = None,
        log_level: int = logging.INFO
    ):
        """
        Inicjalizuje moduł
        
        Args:
            module_name: Nazwa modułu (używana w loggerze)
            module_config_path: Ścieżka do konfiguracji modułu (opcjonalna)
            log_file: Nazwa pliku logów (domyślnie: {module_name}.log)
            log_level: Poziom logowania
        """
        self.module_name = module_name
        self.module_config_path = module_config_path
        self.log_file = log_file or f"{module_name.lower()}.log"
        self.log_level = log_level
        
        # Zasoby do zamknięcia
        self.logger: Optional[logging.Logger] = None
        self.db: Optional[DatabaseConnection] = None
        self.module_config: Dict[str, Any] = {}
        self.global_config: Dict[str, Any] = {}
        
        # Flaga czy moduł został poprawnie zainicjalizowany
        self._initialized = False
    
    def _setup(self) -> bool:
        """
        Wspólna inicjalizacja modułu
        
        Returns:
            True jeśli inicjalizacja się powiodła, False w przeciwnym razie
        """
        try:
            # Inicjalizacja loggera
            self.logger = setup_logger(
                name=self.module_name,
                log_file=self.log_file,
                level=self.log_level
            )
            self.logger.info("<cyan>=</cyan>" * 50)
            self.logger.info(f"<cyan>Uruchamianie modułu {self.module_name}</cyan>")
            self.logger.info("<cyan>=</cyan>" * 50)
            
            # Wczytanie konfiguracji modułu (jeśli podana)
            if self.module_config_path:
                try:
                    self.module_config = load_config(self.module_config_path)
                    self.logger.info("<green>Konfiguracja modułu wczytana pomyślnie</green>")
                except ConfigError as e:
                    self.logger.error(f"<red>Błąd wczytywania konfiguracji modułu: {e}</red>")
                    return False
            
            # Wczytanie konfiguracji globalnej
            try:
                self.global_config = load_config()
            except ConfigError:
                self.global_config = {}
                self.logger.debug("Brak globalnej konfiguracji, używam domyślnych wartości")
            
            # Nawiązanie połączenia z bazą danych
            try:
                self.db = DatabaseConnection()
                self.db.connect()
                self.logger.info("<green>Połączenie z bazą danych nawiązane pomyślnie</green>")
            except DatabaseError as e:
                self.logger.error(f"<red>Błąd połączenia z bazą danych: {e}</red>")
                return False
            
            # Wywołanie metody inicjalizacji specyficznej dla modułu
            if not self._init_module():
                return False
            
            self._initialized = True
            return True
        
        except Exception as e:
            if self.logger:
                self.logger.exception(f"<red>Błąd inicjalizacji modułu: {e}</red>")
            else:
                print(f"Krytyczny błąd inicjalizacji modułu {self.module_name}: {e}")
            return False
    
    def _cleanup(self) -> None:
        """Wspólne zamykanie zasobów"""
        # Zamykanie zasobów specyficznych dla modułu
        try:
            self._cleanup_module()
        except Exception as e:
            if self.logger:
                self.logger.error(f"<red>Błąd podczas zamykania zasobów modułu: {e}</red>")
        
        # Zamykanie połączenia z bazą danych
        if self.db:
            try:
                self.db.disconnect()
                if self.logger:
                    self.logger.info("<green>Połączenie z bazą danych zamknięte</green>")
            except Exception as e:
                if self.logger:
                    self.logger.error(f"<red>Błąd zamykania połączenia: {e}</red>")
        
        # Zakończenie logowania
        if self.logger:
            self.logger.info("<cyan>=</cyan>" * 50)
            self.logger.info(f"<cyan>Zakończenie pracy modułu {self.module_name}</cyan>")
            self.logger.info("<cyan>=</cyan>" * 50)
    
    def run(self) -> int:
        """
        Główna metoda uruchomienia modułu
        
        Returns:
            Kod wyjścia: 0 = sukces, 1 = błąd
        """
        if not self._setup():
            return 1
        
        try:
            # Wywołanie metody specyficznej dla modułu
            result = self.execute()
            return 0 if result else 1
        
        except Exception as e:
            if self.logger:
                self.logger.exception(f"<red>Nieoczekiwany błąd podczas wykonywania modułu: {e}</red>")
            else:
                print(f"Krytyczny błąd: {e}")
            return 1
        
        finally:
            self._cleanup()
    
    @abstractmethod
    def execute(self) -> bool:
        """
        Główna logika modułu - do zaimplementowania w klasach dziedziczących
        
        Returns:
            True jeśli wykonanie się powiodło, False w przeciwnym razie
        """
        pass
    
    def _init_module(self) -> bool:
        """
        Inicjalizacja specyficzna dla modułu - opcjonalna do nadpisania
        
        Returns:
            True jeśli inicjalizacja się powiodła, False w przeciwnym razie
        """
        return True
    
    def _cleanup_module(self) -> None:
        """
        Zamykanie zasobów specyficznych dla modułu - opcjonalna do nadpisania
        """
        pass
    
    def get_config_value(self, key: str, default: Any = None, use_module_config: bool = True) -> Any:
        """
        Pobiera wartość z konfiguracji (najpierw z konfiguracji modułu, potem globalnej)
        
        Args:
            key: Klucz konfiguracji (może być zagnieżdżony, np. "database.timeout")
            default: Wartość domyślna
            use_module_config: Czy używać konfiguracji modułu (True) czy tylko globalnej (False)
        
        Returns:
            Wartość konfiguracji lub wartość domyślna
        """
        if use_module_config and self.module_config:
            value = get_config_value(self.module_config, key)
            if value is not None:
                return value
        
        return get_config_value(self.global_config, key, default)

