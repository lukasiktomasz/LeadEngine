"""
Moduł połączenia z bazą danych MSSQL używając pyodbc
"""

import os
import pyodbc
from typing import Optional, Dict, Any, List, Tuple
from dotenv import load_dotenv
from pathlib import Path


class DatabaseError(Exception):
    """Wyjątek związany z bazą danych"""
    pass


class DatabaseConnection:
    """Klasa zarządzająca połączeniem z bazą danych MSSQL"""
    
    def __init__(self, env_file: str = ".env"):
        """
        Inicjalizuje połączenie z bazą danych
        
        Args:
            env_file: Ścieżka do pliku .env
        """
        # Wczytaj zmienne środowiskowe z pliku .env
        env_path = Path(env_file)
        if env_path.exists():
            load_dotenv(env_path)
        else:
            # Spróbuj wczytać z domyślnej lokalizacji
            load_dotenv()
        
        self.connection: Optional[pyodbc.Connection] = None
        self._load_connection_params()
    
    def _load_connection_params(self) -> None:
        """Wczytuje parametry połączenia z zmiennych środowiskowych"""
        self.server = os.getenv('DB_SERVER')
        self.database = os.getenv('DB_DATABASE')
        self.username = os.getenv('DB_USERNAME')
        self.password = os.getenv('DB_PASSWORD')
        self.driver = os.getenv('DB_DRIVER', '{ODBC Driver 17 for SQL Server}')
        self.trusted_connection = os.getenv('DB_TRUSTED_CONNECTION', 'no').lower() == 'yes'
        
        # Alternatywnie można użyć pełnego connection string
        self.connection_string = os.getenv('DB_CONNECTION_STRING')
        
        if not self.connection_string:
            if not all([self.server, self.database]):
                raise DatabaseError(
                    "Brak wymaganych parametrów połączenia. "
                    "Ustaw DB_SERVER i DB_DATABASE lub DB_CONNECTION_STRING w pliku .env"
                )
    
    def _build_connection_string(self) -> str:
        """Buduje connection string z parametrów"""
        if self.connection_string:
            return self.connection_string
        
        if self.trusted_connection:
            conn_str = (
                f"DRIVER={self.driver};"
                f"SERVER={self.server};"
                f"DATABASE={self.database};"
                f"Trusted_Connection=yes;"
            )
        else:
            if not self.username or not self.password:
                raise DatabaseError("DB_USERNAME i DB_PASSWORD są wymagane dla połączenia z autoryzacją SQL")
            
            conn_str = (
                f"DRIVER={self.driver};"
                f"SERVER={self.server};"
                f"DATABASE={self.database};"
                f"UID={self.username};"
                f"PWD={self.password};"
            )
        
        return conn_str
    
    def connect(self, timeout: int = 30) -> None:
        """
        Nawiązuje połączenie z bazą danych
        
        Args:
            timeout: Timeout połączenia w sekundach
        
        Raises:
            DatabaseError: Gdy nie można nawiązać połączenia
        """
        if self.connection:
            return
        
        try:
            conn_str = self._build_connection_string()
            self.connection = pyodbc.connect(
                conn_str,
                timeout=timeout
            )
        except pyodbc.Error as e:
            error_msg = str(e)
            # Dodaj bardziej przyjazne komunikaty dla typowych błędów
            if "Login failed" in error_msg:
                raise DatabaseError(
                    f"Błąd logowania do bazy danych. Sprawdź:\n"
                    f"- Czy użytkownik '{self.username}' istnieje w SQL Server?\n"
                    f"- Czy hasło jest poprawne?\n"
                    f"- Czy SQL Server Authentication jest włączone?\n"
                    f"Szczegóły: {error_msg}"
                )
            elif "Cannot open database" in error_msg:
                raise DatabaseError(
                    f"Nie można otworzyć bazy danych '{self.database}'. "
                    f"Sprawdź czy baza istnieje i czy użytkownik ma do niej dostęp.\n"
                    f"Szczegóły: {error_msg}"
                )
            else:
                raise DatabaseError(f"Błąd połączenia z bazą danych: {error_msg}")
    
    def disconnect(self) -> None:
        """Zamyka połączenie z bazą danych"""
        if self.connection:
            try:
                self.connection.close()
            except Exception:
                pass
            finally:
                self.connection = None
    
    def execute_query(
        self,
        query: str,
        params: Optional[Tuple] = None,
        fetch: bool = True
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Wykonuje zapytanie SQL
        
        Args:
            query: Zapytanie SQL
            params: Parametry zapytania (dla prepared statements)
            fetch: Czy pobrać wyniki (True) czy tylko wykonać (False)
        
        Returns:
            Lista słowników z wynikami lub None jeśli fetch=False
        
        Raises:
            DatabaseError: Gdy wystąpi błąd podczas wykonywania zapytania
        """
        if not self.connection:
            raise DatabaseError("Brak połączenia z bazą danych. Wywołaj connect() najpierw.")
        
        try:
            cursor = self.connection.cursor()
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            if fetch:
                columns = [column[0] for column in cursor.description]
                results = []
                for row in cursor.fetchall():
                    results.append(dict(zip(columns, row)))
                cursor.close()
                return results
            else:
                self.connection.commit()
                cursor.close()
                return None
        
        except pyodbc.Error as e:
            if self.connection:
                self.connection.rollback()
            raise DatabaseError(f"Błąd wykonania zapytania: {e}")
    
    def test_connection(self) -> bool:
        """
        Testuje połączenie z bazą danych
        
        Returns:
            True jeśli połączenie działa, False w przeciwnym razie
        """
        try:
            if not self.connection:
                self.connect()
            
            result = self.execute_query("SELECT 1 AS test")
            return result is not None and len(result) > 0
        except Exception:
            return False
    
    def __enter__(self):
        """Context manager - wejście"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager - wyjście"""
        self.disconnect()

