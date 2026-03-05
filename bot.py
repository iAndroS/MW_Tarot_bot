import asyncio
import logging
import os
import time
from pathlib import Path
from functools import wraps

from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN
from handlers import register_handlers, set_monitor, register_feedback_handlers
from utils.daily_predictions import DailyPredictionManager
from utils.database import Database
from utils.user_manager import UserManager
from utils.card_manager import CardManager
from utils.monitoring import BotMonitor

def extract_command(update):
    """Извлекает команду из обновления (CallbackQuery или Message)."""
    if isinstance(update, types.CallbackQuery):
        # Для callback query возвращаем data
        cmd = update.data if update.data else "callback_empty"
        return cmd
    # Message - в aiogram 3.x нет get_command(), используем text
    text = update.text or ""
    parts = text.split()
    result = parts[0] if parts else (text if text.startswith('/') else text)
    return result


def log_command(monitor):
    """Декоратор для логирования команд с измерением времени выполнения."""
    def decorator(func):
        @wraps(func)
        async def wrapper(update, *args, **kwargs):
            start_time = time.time()
            # Проверяем наличие from_user для защиты от AttributeError
            if not update.from_user:
                logging.warning("Update without from_user received")
                return None
            user_id = update.from_user.id
            try:
                result = await func(update, *args, **kwargs)
                end_time = time.time()
                
                monitor.log_command(
                    user_id,
                    extract_command(update),
                    True,
                    end_time - start_time
                )
                return result
            except Exception as e:
                end_time = time.time()
                
                monitor.log_command(
                    user_id,
                    extract_command(update),
                    False,
                    end_time - start_time
                )
                monitor.log_error(
                    error_type=type(e).__name__,
                    error_message=str(e),
                    user_id=user_id
                )
                raise
        return wrapper
    return decorator

class BotManager:
    def __init__(self):
        self.bot = Bot(
            token=BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
        )
        self.storage = MemoryStorage()
        self.dp = Dispatcher(storage=self.storage)
        self.daily_prediction_manager = DailyPredictionManager(self.bot)
        self.db = Database()
        self._cleanup_tasks = []
        
        # Инициализируем монитор
        self.monitor = BotMonitor()
        logging.info("BotMonitor initialized")
        
        # Устанавливаем глобальный монитор в handlers (set_monitor уже импортирован)
        set_monitor(self.monitor)
        logging.info("Monitor set in handlers module")
    
    async def on_startup(self, dp: Dispatcher):
        """Действия при запуске бота."""
        self.monitor.logger.info("=" * 50)
        self.monitor.logger.info("Запуск бота")
        self.monitor.logger.info(f"Python version: {os.sys.version}")
        self.monitor.logger.info(f"Working directory: {os.getcwd()}")
        
        # Инициализируем менеджеры
        self.monitor.logger.info("Initializing UserManager...")
        self.user_manager = UserManager()
        self.monitor.logger.info("Initializing CardManager...")
        self.card_manager = CardManager()
        
        # Инициализируем карты
        self.monitor.logger.info("Initializing cards...")
        await self.card_manager.initialize()
        self.monitor.logger.info("Cards initialized successfully")
        
        # Запускаем периодическую очистку кэша
        await self.user_manager.cache.start_cleanup()
        await self.card_manager.cache.start_cleanup()
        
        # Регистрируем хендлеры с декоратором логирования
        register_handlers(dp, log_command(self.monitor))
        
        # Проверяем наличие файлов обратной связи
        current_dir = Path(__file__).parent
        feedback_path = current_dir / "utils" / "feedback.py"
        handlers_path = current_dir / "handlers" / "feedback_handlers.py"
        
        if feedback_path.exists() and handlers_path.exists():
            try:
                register_feedback_handlers(dp)
                self.monitor.logger.info("Обработчики обратной связи зарегистрированы")
            except ImportError as e:
                self.monitor.logger.warning(f"Не удалось загрузить модуль обратной связи: {e}")
                self.monitor.logger.warning(f"Пути: feedback={feedback_path}, handlers={handlers_path}")
        else:
            self.monitor.logger.info(f"Модуль обратной связи отключен. Файлы не найдены: feedback={not feedback_path.exists()}, handlers={not handlers_path.exists()}")
        
        # Запускаем периодическую отправку предсказаний
        self._cleanup_tasks.append(
            asyncio.create_task(self.daily_prediction_manager.schedule_daily_predictions())
        )
        
        # Запускаем мониторинг ресурсов
        self._cleanup_tasks.append(
            asyncio.create_task(self.monitor.monitor_resources())
        )
    
    async def on_shutdown(self, dp: Dispatcher):
        """Действия при остановке бота."""
        self.monitor.logger.info("Остановка бота")
        
        # Останавливаем периодическую очистку кэша
        await self.user_manager.cache.stop_cleanup()
        await self.card_manager.cache.stop_cleanup()
        
        # Сохраняем финальную статистику
        await self.monitor.save_stats()
        
        # Отменяем все фоновые задачи
        for task in self._cleanup_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    
    async def run_async(self):
        """Асинхронный запуск бота."""
        try:
            await self.on_startup(self.dp)
            await self.dp.start_polling(self.bot, skip_updates=True)
        finally:
            await self.on_shutdown(self.dp)
            await self.bot.session.close()

    def run(self):
        """Запуск бота."""
        asyncio.run(self.run_async())

if __name__ == '__main__':
    bot_manager = BotManager()
    bot_manager.run()