"""
Szablon modułu - przykład użycia BaseModule
Ten plik pokazuje jak utworzyć nowy moduł dziedziczący po BaseModule
"""

import sys
from pathlib import Path

# Dodaj katalog główny do ścieżki
sys.path.insert(0, str(Path(__file__).parent))

from common.base_module import BaseModule
from common.database import DatabaseError


class ExampleModule(BaseModule):
    """
    Przykładowy moduł - szablon do tworzenia nowych modułów
    
    Aby utworzyć nowy moduł:
    1. Skopiuj ten plik do modules/twoj_modul/main.py
    2. Zmień nazwę klasy na TwojModulModule
    3. Zaimplementuj metodę execute() z własną logiką
    4. Opcjonalnie nadpisz _init_module() i _cleanup_module()
    """
    
    def __init__(self):
        super().__init__(
            module_name="ExampleModule",
            # module_config_path="modules/twoj_modul/config.json",  # Opcjonalne
            log_file="example_module.log"
        )
    
    def execute(self) -> bool:
        """
        Główna logika modułu - zaimplementuj tutaj swoją funkcjonalność
        
        Returns:
            True jeśli wykonanie się powiodło, False w przeciwnym razie
        """
        # Przykład: test połączenia z bazą danych
        if self.db.test_connection():
            self.logger.info("<green>Test połączenia z bazą danych: OK</green>")
        else:
            self.logger.warning("<red>Test połączenia z bazą danych: Niepowodzenie</red>")
            return False
        
        # Przykładowe zapytanie
        try:
            result = self.db.execute_query("SELECT @@VERSION AS sql_version")
            if result:
                version = result[0].get('sql_version', 'N/A')[:50]
                self.logger.info(f"<yellow>Wersja SQL Server: {version}...</yellow>")
        except DatabaseError as e:
            self.logger.error(f"<red>Błąd wykonania zapytania: {e}</red>")
            return False
        
        # Tutaj dodaj swoją logikę modułu
        self.logger.info("<yellow>Główna logika modułu zakończona pomyślnie</yellow>")
        
        return True
    
    # Opcjonalnie: nadpisz _init_module() jeśli potrzebujesz dodatkowej inicjalizacji
    # def _init_module(self) -> bool:
    #     # Twoja dodatkowa inicjalizacja
    #     return True
    
    # Opcjonalnie: nadpisz _cleanup_module() jeśli potrzebujesz zamknąć dodatkowe zasoby
    # def _cleanup_module(self) -> None:
    #     # Zamykanie dodatkowych zasobów
    #     pass


def main():
    """Główna funkcja modułu"""
    module = ExampleModule()
    return module.run()


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

