"""
Moduł website_scraper - pobieranie danych firm z witryn internetowych
"""

from .engine import ScrapingEngine
from .base_parser import BaseParser
from .parsers.targi_kielce import TargiKielceParser

__all__ = ['ScrapingEngine', 'BaseParser', 'TargiKielceParser']
