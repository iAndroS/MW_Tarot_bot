"""
Тесты для settings.py - валидация ADMIN_IDS.
"""
import pytest
import logging
from unittest.mock import patch, MagicMock
import importlib
import sys


class TestAdminIdsParsing:
    """Тесты парсинга ADMIN_IDS из переменных окружения."""

    def test_single_admin_id(self, monkeypatch, mock_env_vars):
        """Тест корректного парсинга одного ADMIN_ID."""
        mock_env_vars({"ADMIN_IDS": "12345"})
        
        # Очищаем кэш импорта для перезагрузки модуля
        if 'settings' in sys.modules:
            del sys.modules['settings']
        
        with patch('dotenv.load_dotenv'):
            import settings
            importlib.reload(settings)
        
        assert settings.ADMIN_IDS == [12345]

    def test_multiple_admin_ids(self, monkeypatch, mock_env_vars):
        """Тест корректного парсинга нескольких ADMIN_ID через запятую."""
        mock_env_vars({"ADMIN_IDS": "12345,67890,11111"})
        
        if 'settings' in sys.modules:
            del sys.modules['settings']
        
        with patch('dotenv.load_dotenv'):
            import settings
            importlib.reload(settings)
        
        assert settings.ADMIN_IDS == [12345, 67890, 11111]

    def test_admin_ids_with_spaces(self, monkeypatch, mock_env_vars):
        """Тест игнорирования пробелов вокруг ID."""
        mock_env_vars({"ADMIN_IDS": " 12345 , 67890 , 11111 "})
        
        if 'settings' in sys.modules:
            del sys.modules['settings']
        
        with patch('dotenv.load_dotenv'):
            import settings
            importlib.reload(settings)
        
        assert settings.ADMIN_IDS == [12345, 67890, 11111]

    def test_empty_strings_ignored(self, monkeypatch, mock_env_vars, caplog):
        """Тест игнорирования пустых строк между запятыми."""
        mock_env_vars({"ADMIN_IDS": "12345,,67890"})
        
        if 'settings' in sys.modules:
            del sys.modules['settings']
        
        with patch('dotenv.load_dotenv'):
            import settings
            importlib.reload(settings)
        
        # Пустая строка должна вызвать ValueError и быть пропущена
        assert settings.ADMIN_IDS == [12345, 67890]

    def test_negative_ids_logged_and_ignored(self, monkeypatch, mock_env_vars, caplog):
        """Тест игнорирования отрицательных ID с проверкой логирования."""
        mock_env_vars({"ADMIN_IDS": "12345,-67890,11111"})
        
        if 'settings' in sys.modules:
            del sys.modules['settings']
        
        with caplog.at_level(logging.WARNING):
            with patch('dotenv.load_dotenv'):
                import settings
                importlib.reload(settings)
        
        assert settings.ADMIN_IDS == [12345, 11111]
        assert "Пропущен отрицательный ADMIN_ID" in caplog.text
        assert "-67890" in caplog.text

    def test_non_numeric_ids_logged_and_ignored(self, monkeypatch, mock_env_vars, caplog):
        """Тест игнорирования нечисловых значений с проверкой логирования."""
        mock_env_vars({"ADMIN_IDS": "12345,abc,11111"})
        
        if 'settings' in sys.modules:
            del sys.modules['settings']
        
        with caplog.at_level(logging.WARNING):
            with patch('dotenv.load_dotenv'):
                import settings
                importlib.reload(settings)
        
        assert settings.ADMIN_IDS == [12345, 11111]
        assert "Некорректный ADMIN_ID" in caplog.text
        assert "abc" in caplog.text

    def test_empty_admin_ids_returns_empty_list(self, monkeypatch, mock_env_vars):
        """Тест пустого значения ADMIN_IDS (должен вернуться пустой список)."""
        mock_env_vars({"ADMIN_IDS": ""})
        
        if 'settings' in sys.modules:
            del sys.modules['settings']
        
        with patch('dotenv.load_dotenv'):
            import settings
            importlib.reload(settings)
        
        assert settings.ADMIN_IDS == []

    def test_whitespace_only_admin_ids_returns_empty_list(self, monkeypatch, mock_env_vars):
        """Тест значения ADMIN_IDS из одних пробелов."""
        mock_env_vars({"ADMIN_IDS": "   "})
        
        if 'settings' in sys.modules:
            del sys.modules['settings']
        
        with patch('dotenv.load_dotenv'):
            import settings
            importlib.reload(settings)
        
        assert settings.ADMIN_IDS == []

    def test_mixed_invalid_ids(self, monkeypatch, mock_env_vars, caplog):
        """Тест смешанных валидных и невалидных ID."""
        mock_env_vars({"ADMIN_IDS": "12345,abc,-999,67890,xyz,0"})
        
        if 'settings' in sys.modules:
            del sys.modules['settings']
        
        with caplog.at_level(logging.WARNING):
            with patch('dotenv.load_dotenv'):
                import settings
                importlib.reload(settings)
        
        # 0 не должен быть включён (только > 0)
        assert settings.ADMIN_IDS == [12345, 67890]
        assert "Некорректный ADMIN_ID" in caplog.text
        assert "Пропущен отрицательный ADMIN_ID" in caplog.text


class TestBotSettings:
    """Тесты остальных настроек бота."""

    def test_max_daily_spreads(self, monkeypatch, mock_env_vars):
        """Тест константы MAX_DAILY_SPREADS."""
        mock_env_vars({"ADMIN_IDS": "12345"})
        
        if 'settings' in sys.modules:
            del sys.modules['settings']
        
        with patch('dotenv.load_dotenv'):
            import settings
            importlib.reload(settings)
        
        assert settings.MAX_DAILY_SPREADS == 3

    def test_file_paths(self, monkeypatch, mock_env_vars):
        """Тест путей к файлам."""
        mock_env_vars({"ADMIN_IDS": "12345"})
        
        if 'settings' in sys.modules:
            del sys.modules['settings']
        
        with patch('dotenv.load_dotenv'):
            import settings
            importlib.reload(settings)
        
        assert settings.TAROT_DECK_FILE == "data/tarot_deck.json"
        assert settings.SAVED_SPREADS_FILE == "data/saved_spreads.json"
        assert settings.USER_DATA_FILE == "data/user_data.json"

    def test_default_theme(self, monkeypatch, mock_env_vars):
        """Тест значения DEFAULT_THEME."""
        mock_env_vars({"ADMIN_IDS": "12345"})
        
        if 'settings' in sys.modules:
            del sys.modules['settings']
        
        with patch('dotenv.load_dotenv'):
            import settings
            importlib.reload(settings)
        
        assert settings.DEFAULT_THEME == "light"
        assert settings.SHOW_CARD_IMAGES is True
