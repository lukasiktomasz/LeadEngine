"""
Parsery dla różnych stron źródłowych
"""

# Import zależny od sposobu uruchomienia
try:
    from ..base_parser import BaseParser
    from .targi_kielce import TargiKielceParser
except ImportError:
    pass  # Importy zostaną wykonane bezpośrednio w plikach

__all__ = ['BaseParser', 'TargiKielceParser']
