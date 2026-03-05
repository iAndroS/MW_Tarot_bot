import logging
import logging.handlers
import psutil
import os
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List
import asyncio
from pathlib import Path
import aiofiles
import platform

class BotMonitor:
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Статистика
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "command_usage": {},
            "errors": {},
            "user_activity": {},
            "peak_memory": 0,
            "peak_cpu": 0,
            "start_time": datetime.now().isoformat(),
            "hourly_stats": {str(i): 0 for i in range(24)},  # Статистика по часам
            "daily_stats": {},  # Статистика по дням
            "response_times": [],  # Времена ответа
            "system_info": {  # Информация о системе
                "os": platform.system(),
                "python_version": platform.python_version(),
                "cpu_count": psutil.cpu_count(),
                "total_memory": psutil.virtual_memory().total
            }
        }
        
        # Настройка логирования
        self._setup_logging()
    
    def _setup_logging(self):
        """Настройка системы логирования."""
        # Основной логгер
        self.logger = logging.getLogger('bot_logger')
        self.logger.setLevel(logging.DEBUG)
        
        # Форматтер для логов
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Обработчик для всех логов
        all_handler = logging.handlers.RotatingFileHandler(
            self.log_dir / 'bot.log',
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        all_handler.setFormatter(formatter)
        all_handler.setLevel(logging.INFO)
        
        # Обработчик для ошибок
        error_handler = logging.handlers.RotatingFileHandler(
            self.log_dir / 'errors.log',
            maxBytes=10*1024*1024,
            backupCount=5,
            encoding='utf-8'
        )
        error_handler.setFormatter(formatter)
        error_handler.setLevel(logging.ERROR)
        
        # Обработчик для отладки
        debug_handler = logging.handlers.RotatingFileHandler(
            self.log_dir / 'debug.log',
            maxBytes=10*1024*1024,
            backupCount=3,
            encoding='utf-8'
        )
        debug_handler.setFormatter(formatter)
        debug_handler.setLevel(logging.DEBUG)
        
        # Добавляем обработчики к логгеру
        self.logger.addHandler(all_handler)
        self.logger.addHandler(error_handler)
        self.logger.addHandler(debug_handler)
        
        # Консольный вывод
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.INFO)
        self.logger.addHandler(console_handler)
    
    def log_command(self, user_id: int, command: str, success: bool = True, response_time: float = None):
        """Расширенное логирование использования команды."""
        # Обновляем базовую статистику
        self.stats["total_requests"] += 1
        if success:
            self.stats["successful_requests"] += 1
        else:
            self.stats["failed_requests"] += 1
        
        # Обновляем статистику команд
        self.stats["command_usage"][command] = self.stats["command_usage"].get(command, 0) + 1
        
        # Обновляем почасовую статистику
        current_hour = str(datetime.now().hour)
        self.stats["hourly_stats"][current_hour] = self.stats["hourly_stats"].get(current_hour, 0) + 1
        
        # Обновляем дневную статистику
        current_date = datetime.now().date().isoformat()
        if current_date not in self.stats["daily_stats"]:
            self.stats["daily_stats"][current_date] = {
                "total": 0,
                "successful": 0,
                "failed": 0,
                "commands": {}
            }
        self.stats["daily_stats"][current_date]["total"] += 1
        if success:
            self.stats["daily_stats"][current_date]["successful"] += 1
        else:
            self.stats["daily_stats"][current_date]["failed"] += 1
        
        # Сохраняем время ответа
        if response_time is not None:
            self.stats["response_times"].append(response_time)
            # Оставляем только последние 1000 значений
            if len(self.stats["response_times"]) > 1000:
                self.stats["response_times"] = self.stats["response_times"][-1000:]
        
        # Обновляем активность пользователя
        user_key = str(user_id)
        if user_key not in self.stats["user_activity"]:
            self.stats["user_activity"][user_key] = {
                "commands": {},
                "last_activity": None,
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "first_seen": datetime.now().isoformat()
            }
        
        user_stats = self.stats["user_activity"][user_key]
        user_stats["commands"][command] = user_stats["commands"].get(command, 0) + 1
        user_stats["last_activity"] = datetime.now().isoformat()
        user_stats["total_requests"] += 1
        if success:
            user_stats["successful_requests"] += 1
        else:
            user_stats["failed_requests"] += 1
        
        self.logger.info(
            f"Command: {command} | User: {user_id} | Success: {success} | "
            f"Response time: {response_time:.3f}s" if response_time else "N/A"
        )
    
    def log_error(self, error_type: str, error_message: str, user_id: int = None):
        """Логирование ошибок."""
        if error_type not in self.stats["errors"]:
            self.stats["errors"][error_type] = {
                "count": 0,
                "last_occurrence": None,
                "users_affected": set()
            }
        
        # Гарантируем что users_affected всегда set (после десериализации может стать list)
        affected = self.stats["errors"][error_type]["users_affected"]
        if isinstance(affected, list):
            self.stats["errors"][error_type]["users_affected"] = set(affected)
        elif not isinstance(affected, set):
            self.stats["errors"][error_type]["users_affected"] = set()
        
        self.stats["errors"][error_type]["count"] += 1
        self.stats["errors"][error_type]["last_occurrence"] = datetime.now().isoformat()
        if user_id:
            self.stats["errors"][error_type]["users_affected"].add(user_id)
        
        self.logger.error(
            f"Error: {error_type} | Message: {error_message} | User: {user_id}"
        )
    
    async def monitor_resources(self):
        """Мониторинг системных ресурсов."""
        while True:
            try:
                # Получаем текущие показатели
                cpu_percent = psutil.cpu_percent()
                memory = psutil.Process().memory_info()
                memory_percent = memory.rss / psutil.virtual_memory().total * 100
                
                # Обновляем пиковые значения
                self.stats["peak_cpu"] = max(self.stats["peak_cpu"], cpu_percent)
                self.stats["peak_memory"] = max(self.stats["peak_memory"], memory_percent)
                
                # Логируем текущее состояние
                self.logger.info(
                    f"Системные ресурсы:\n"
                    f"CPU: {cpu_percent}% (пик: {self.stats['peak_cpu']}%)\n"
                    f"Память: {memory.rss / 1024 / 1024:.1f} MB ({memory_percent:.1f}%)\n"
                    f"Пиковая память: {self.stats['peak_memory']:.1f}%\n"
                    f"Всего запросов: {self.stats['total_requests']}\n"
                    f"Успешных: {self.stats['successful_requests']}\n"
                    f"Ошибок: {self.stats['failed_requests']}"
                )
                
                # Сохраняем статистику
                await self.save_stats()
                
                await asyncio.sleep(300)  # Каждые 5 минут
                
            except Exception as e:
                self.logger.error(f"Ошибка при мониторинге ресурсов: {e}")
                await asyncio.sleep(60)
    
    async def save_stats(self):
        """Сохранение статистики в файл."""
        try:
            # Конвертируем set в list для JSON
            stats_copy = self.stats.copy()
            for error_type in stats_copy["errors"]:
                stats_copy["errors"][error_type]["users_affected"] = \
                    list(self.stats["errors"][error_type]["users_affected"])
            
            stats_file = self.log_dir / 'stats.json'
            async with aiofiles.open(stats_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(stats_copy, indent=2, ensure_ascii=False))
        
        except Exception as e:
            self.logger.error(f"Ошибка при сохранении статистики: {e}")
    
    def get_stats_report(self) -> str:
        """Получение расширенного отчета о статистике."""
        uptime = datetime.now() - datetime.fromisoformat(self.stats["start_time"])
        
        # Вычисляем среднее время ответа
        avg_response_time = (
            sum(self.stats["response_times"]) / len(self.stats["response_times"])
            if self.stats["response_times"] else 0
        )
        
        # Находим самые активные часы
        peak_hour = max(self.stats["hourly_stats"].items(), key=lambda x: x[1])
        
        # Считаем активных пользователей за последние 24 часа
        active_users_24h = sum(
            1 for user in self.stats["user_activity"].values()
            if datetime.fromisoformat(user["last_activity"]) > datetime.now() - timedelta(days=1)
        )
        
        report = (
            f"📊 *Общая статистика*\n"
            f"⏱ Время работы: {uptime.days}д {uptime.seconds//3600}ч {(uptime.seconds//60)%60}м\n"
            f"📝 Всего запросов: {self.stats['total_requests']}\n"
            f"✅ Успешных: {self.stats['successful_requests']}\n"
            f"❌ Ошибок: {self.stats['failed_requests']}\n"
            f"👥 Активных пользователей (24ч): {active_users_24h}\n\n"
            
            f"⚡️ *Производительность*\n"
            f"CPU: {psutil.cpu_percent()}% (пик: {self.stats['peak_cpu']}%)\n"
            f"RAM: {psutil.Process().memory_info().rss / 1024 / 1024:.1f}MB\n"
            f"Среднее время ответа: {avg_response_time*1000:.1f}мс\n\n"
            
            f"📈 *Активность*\n"
            f"Пиковый час: {peak_hour[0]}:00 ({peak_hour[1]} запросов)\n\n"
            
            f"🔝 *Топ команд:*\n"
        )
        
        # Добавляем топ-5 команд
        sorted_commands = sorted(
            self.stats["command_usage"].items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        for command, count in sorted_commands:
            report += f"/{command}: {count} раз\n"
        
        # Добавляем информацию об ошибках
        if self.stats["errors"]:
            report += "\n❌ *Последние ошибки:*\n"
            for error_type, error_info in list(self.stats["errors"].items())[:3]:
                report += (
                    f"{error_type}: {error_info['count']} раз\n"
                    f"└ Последняя: {error_info['last_occurrence']}\n"
                )
        
        return report 