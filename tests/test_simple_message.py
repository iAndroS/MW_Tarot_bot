"""
Тесты для SimpleMessage класса в handlers.
"""
import pytest
from unittest.mock import MagicMock
from handlers.handlers import SimpleMessage


class TestSimpleMessage:
    """Тесты класса SimpleMessage."""

    def test_simple_message_with_valid_callback(self, mock_callback):
        """Тест создания SimpleMessage с валидным callback."""
        message = SimpleMessage(mock_callback)
        
        assert message.chat is not None
        assert message.chat.id == 12345
        assert message.message_id == 67890
        assert message.from_user is not None
        assert message.from_user.id == 11111
        assert message.from_user.username == "test_user"
        assert message.bot is not None

    def test_simple_message_when_callback_message_is_none(self, mock_callback_no_message):
        """Тест создания SimpleMessage когда callback.message is None."""
        message = SimpleMessage(mock_callback_no_message)
        
        assert message.chat is None
        assert message.message_id is None
        assert message.from_user is not None
        assert message.from_user.id == 11111
        assert message.from_user.username == "test_user"
        assert message.bot is not None

    def test_simple_message_attributes_set_correctly(self):
        """Тест что атрибуты chat, message_id, from_user, bot установлены корректно."""
        # Создаём полностью кастомный мок
        callback = MagicMock()
        callback.message.chat.id = 99999
        callback.message.message_id = 88888
        callback.from_user.id = 77777
        callback.from_user.first_name = "Test"
        callback.bot.token = "test_token"
        
        message = SimpleMessage(callback)
        
        # Проверяем все атрибуты
        assert message.chat.id == 99999
        assert message.message_id == 88888
        assert message.from_user.id == 77777
        assert message.from_user.first_name == "Test"
        assert message.bot.token == "test_token"

    def test_simple_message_partial_none_message(self):
        """Тест SimpleMessage когда message существует но имеет None атрибуты."""
        callback = MagicMock()
        callback.message.chat = None
        callback.message.message_id = None
        callback.from_user.id = 12345
        callback.bot = MagicMock()
        
        message = SimpleMessage(callback)
        
        assert message.chat is None
        assert message.message_id is None
        assert message.from_user.id == 12345

    def test_simple_message_preserves_bot_reference(self):
        """Тест что SimpleMessage сохраняет ссылку на bot."""
        callback = MagicMock()
        callback.message.chat.id = 111
        callback.message.message_id = 222
        callback.from_user.id = 333
        bot_mock = MagicMock()
        bot_mock.send_message = MagicMock()
        callback.bot = bot_mock
        
        message = SimpleMessage(callback)
        
        assert message.bot == bot_mock
        assert hasattr(message.bot, 'send_message')
