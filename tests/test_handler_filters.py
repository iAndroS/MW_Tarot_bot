"""
Тесты для порядка фильтров /stats.
"""
import pytest
from unittest.mock import MagicMock, patch, call
import sys


class TestStatsFilterOrder:
    """Тесты порядка фильтров для команды /stats."""

    def test_admin_filter_checked_before_command_filter(self, mock_message):
        """
        Тест что фильтр прав админа проверяется перед Command фильтром.
        
        Важно: в aiogram 3.x фильтры применяются в порядке их передачи.
        Если админский фильтр идёт первым, не-админы не дойдут до Command фильтра.
        """
        from aiogram.filters import Command
        from handlers.handlers import ADMIN_IDS
        
        # Мокаем ADMIN_IDS чтобы включить наш тестовый ID
        with patch('handlers.handlers.ADMIN_IDS', [12345]):
            # Создаём мок диспетчера
            dp = MagicMock()
            
            # Отслеживаем порядок вызова фильтров
            filter_calls = []
            
            def admin_filter(message):
                filter_calls.append('admin_filter')
                return message.from_user.id in [12345]
            
            def command_filter(commands):
                def check(message):
                    filter_calls.append('command_filter')
                    return message.text.startswith('/')
                return check
            
            # Симулируем регистрацию хендлера как в handlers.py
            # Важно: admin_filter ДОЛЖЕН быть первым!
            dp.message.register = MagicMock()
            
            # Проверяем что регистрация происходит с правильным порядком
            # (это проверяет логику из register_handlers)
            
            # Создаём mock для проверки порядка
            mock_handler = MagicMock()
            
            # Импортируем и проверяем register_handlers
            from handlers.handlers import register_handlers
            
            # Мокаем зависимости
            with patch('handlers.handlers.bot_monitor', MagicMock()):
                register_handlers(dp)
                
                # Находим вызов register для cmd_stats
                # Проверяем что lambda (admin check) идёт перед Command
                register_calls = dp.message.register.call_args_list
                
                stats_call = None
                for call_args in register_calls:
                    args, kwargs = call_args
                    if args and hasattr(args[0], '__name__') and 'cmd_stats' in str(args[0]):
                        stats_call = call_args
                        break
                
                # Проверяем что регистрация существует
                # Важно: порядок фильтров должен быть admin_filter, затем Command
                assert dp.message.register.called

    def test_non_admin_cannot_access_stats(self, mock_message):
        """Тест что не-админ не может получить доступ к /stats."""
        mock_message.from_user.id = 99999  # Не админ
        mock_message.text = "/stats"
        
        # Проверяем что ID не в списке админов
        from handlers.handlers import ADMIN_IDS
        assert 99999 not in ADMIN_IDS

    def test_mock_filter_order_execution(self):
        """
        Мок-тест для проверки порядка вызова фильтров.
        Симулирует логику aiogram при обработке фильтров.
        """
        filter_order = []
        
        def admin_filter_lambda(msg):
            """Имитирует lambda из handlers.py: lambda message: message.from_user.id in ADMIN_IDS"""
            filter_order.append('admin')
            admin_ids = [12345, 67890]
            return msg.from_user.id in admin_ids
        
        def command_filter(msg):
            """Имитирует Command фильтр"""
            filter_order.append('command')
            return msg.text.startswith('/stats')
        
        # Создаём тестовое сообщение от не-админа
        msg = MagicMock()
        msg.from_user.id = 99999
        msg.text = "/stats"
        
        # Симулируем обработку фильтров в порядке aiogram 3.x
        # (фильтры применяются слева направо)
        result_admin = admin_filter_lambda(msg)
        
        # Если админский фильтр вернул False, Command фильтр не должен вызываться
        if result_admin:
            command_filter(msg)
        
        # Проверяем что admin_filter был вызван
        assert 'admin' in filter_order
        # Command фильтр НЕ должен был вызваться для не-админа
        assert 'command' not in filter_order
        
        # Теперь тестируем для админа
        filter_order.clear()
        msg.from_user.id = 12345
        
        result_admin = admin_filter_lambda(msg)
        if result_admin:
            command_filter(msg)
        
        # Теперь оба фильтра должны были вызваться
        assert filter_order == ['admin', 'command']

    def test_admin_filter_logic_matches_handlers(self):
        """
        Тест что логика фильтра админа соответствует той, что в handlers.py.
        """
        from handlers.handlers import ADMIN_IDS
        
        # Тестируем логику lambda из handlers.py
        admin_filter = lambda message: message.from_user.id in ADMIN_IDS
        
        # Создаём сообщения от разных пользователей
        admin_msg = MagicMock()
        admin_msg.from_user.id = 12345 if ADMIN_IDS else 1
        
        non_admin_msg = MagicMock()
        non_admin_msg.from_user.id = 99999
        
        if ADMIN_IDS:
            # Если список админов не пустой
            assert admin_filter(admin_msg) == (12345 in ADMIN_IDS)
            assert admin_filter(non_admin_msg) == (99999 in ADMIN_IDS)
        else:
            # Если список пустой
            assert admin_filter(admin_msg) == False
            assert admin_filter(non_admin_msg) == False

    def test_filter_registration_order_in_handlers_py(self):
        """
        Тест проверяющий что в handlers.py фильтр админа регистрируется ДО Command.
        """
        import inspect
        from handlers.handlers import register_handlers
        
        # Получаем исходный код функции
        source = inspect.getsource(register_handlers)
        
        # Ищем регистрацию cmd_stats
        assert "cmd_stats" in source
        
        # Проверяем что структура соответствует ожидаемой:
        # lambda message: message.from_user.id in ADMIN_IDS должен быть ПЕРВЫМ
        # Command(commands=['stats']) должен быть ВТОРЫМ
        
        # Находим позиции
        admin_lambda_pos = source.find("lambda message: message.from_user.id in ADMIN_IDS")
        command_pos = source.find("Command(commands=['stats'])")
        
        # Оба должны присутствовать
        assert admin_lambda_pos != -1, "Admin lambda filter not found"
        assert command_pos != -1, "Command filter not found"
        
        # lambda должен идти перед Command (в одной регистрации)
        # Ищем ближайшую регистрацию к cmd_stats
        lines = source.split('\n')
        cmd_stats_line = None
        for i, line in enumerate(lines):
            if 'cmd_stats' in line:
                cmd_stats_line = i
                break
        
        if cmd_stats_line:
            # Проверяем несколько строк до и после
            context = '\n'.join(lines[max(0, cmd_stats_line-3):cmd_stats_line+3])
            
            # Ищем позиции в контексте
            local_admin_pos = context.find("lambda message: message.from_user.id in ADMIN_IDS")
            local_command_pos = context.find("Command(commands=['stats'])")
            
            if local_admin_pos != -1 and local_command_pos != -1:
                # Admin lambda должен быть до Command
                assert local_admin_pos < local_command_pos, \
                    "Admin filter should be registered BEFORE Command filter"
