"""
Moduł odczytu konfiguracji z pliku JSON
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional


class ConfigError(Exception):
    """Wyjątek związany z konfiguracją"""
    pass


def load_config(config_path: str = "config/config.json") -> Dict[str, Any]:
    """
    Wczytuje konfigurację z pliku JSON
    
    Args:
        config_path: Ścieżka do pliku konfiguracyjnego
    
    Returns:
        Słownik z konfiguracją
    
    Raises:
        ConfigError: Gdy plik nie istnieje lub jest nieprawidłowy
    """
    config_file = Path(config_path)
    
    if not config_file.exists():
        raise ConfigError(f"Plik konfiguracyjny nie istnieje: {config_path}")
    
    if not config_file.is_file():
        raise ConfigError(f"Ścieżka nie wskazuje na plik: {config_path}")
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        if not isinstance(config, dict):
            raise ConfigError("Plik konfiguracyjny musi zawierać obiekt JSON")
        
        return config
    
    except json.JSONDecodeError as e:
        raise ConfigError(f"Błąd parsowania JSON: {e}")
    except Exception as e:
        raise ConfigError(f"Błąd odczytu pliku konfiguracyjnego: {e}")


def get_config_value(config: Dict[str, Any], key: str, default: Any = None) -> Any:
    """
    Pobiera wartość z konfiguracji z obsługą wartości domyślnej
    
    Args:
        config: Słownik konfiguracji
        key: Klucz do pobrania (może być zagnieżdżony, np. "database.host")
        default: Wartość domyślna jeśli klucz nie istnieje
    
    Returns:
        Wartość konfiguracji lub wartość domyślna
    """
    keys = key.split('.')
    value = config
    
    try:
        for k in keys:
            value = value[k]
        return value
    except (KeyError, TypeError):
        return default

