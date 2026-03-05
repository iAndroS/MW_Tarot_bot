"""
Фикстуры для тестов.
"""
import pytest
import os
import sys
from unittest.mock import MagicMock, AsyncMock


# Добавляем корневую директорию проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Фикстура для мокирования переменных окружения."""
    def _set_env(vars_dict):
        for key, value in vars_dict.items():
            monkeypatch.setenv(key, value)
    return _set_env


@pytest.fixture
def clear_env_vars(monkeypatch):
    """Фикстура для очистки переменных окружения."""
    def _clear_env(var_names):
        for name in var_names:
            monkeypatch.delenv(name, raising=False)
    return _clear_env


@pytest.fixture
def mock_callback():
    """Создаёт мок-объект callback для тестов SimpleMessage."""
    callback = MagicMock()
    callback.message.chat.id = 12345
    callback.message.message_id = 67890
    callback.from_user.id = 11111
    callback.from_user.username = "test_user"
    callback.bot = MagicMock()
    return callback


@pytest.fixture
def mock_callback_no_message():
    """Создаёт мок-объект callback без message для тестов SimpleMessage."""
    callback = MagicMock()
    callback.message = None
    callback.from_user.id = 11111
    callback.from_user.username = "test_user"
    callback.bot = MagicMock()
    return callback


@pytest.fixture
def mock_message():
    """Создаёт мок-объект message для тестов фильтров."""
    message = MagicMock()
    message.from_user.id = 12345
    message.text = "/stats"
    return message
