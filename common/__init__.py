"""
Część wspólna projektu LeadEngine
Moduły używane przez wszystkie moduły funkcjonalne
"""

from .logger import setup_logger
from .database import DatabaseConnection, DatabaseError
from .config import load_config, get_config_value, ConfigError
from .base_module import BaseModule

__all__ = [
    'setup_logger',
    'DatabaseConnection',
    'DatabaseError',
    'load_config',
    'get_config_value',
    'ConfigError',
    'BaseModule',
]

__version__ = "1.0.0"

