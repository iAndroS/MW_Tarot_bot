import os
import logging
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Bot settings
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# Безопасное логирование токена (только факт наличия)
if BOT_TOKEN:
    logging.info("BOT_TOKEN loaded successfully")
else:
    logging.warning("BOT_TOKEN is NOT SET in environment variables")

# Проверка наличия токена с мягкой обработкой
if not BOT_TOKEN:
    logging.error("BOT_TOKEN is required but not set. Bot may not function correctly.")
    # Не вызываем RuntimeError, чтобы бот мог запуститься с ограниченным функционалом

MAX_DAILY_SPREADS = 3  # Максимальное количество раскладов в день

# Список ID администраторов (загружается из .env)
admin_ids_str = os.getenv("ADMIN_IDS", "").strip()
ADMIN_IDS = []
if admin_ids_str:
    for id_str in admin_ids_str.split(","):
        id_str = id_str.strip()
        try:
            admin_id = int(id_str)
            if admin_id > 0:
                ADMIN_IDS.append(admin_id)
            else:
                logging.warning(f"Пропущен отрицательный ADMIN_ID: {id_str}")
        except ValueError:
            logging.warning(f"Некорректный ADMIN_ID: {id_str}")

# Логируем только количество админов (без ID)
admin_count = len(ADMIN_IDS)
logging.info(f"ADMIN_IDS loaded: {admin_count} admin(s) configured")

# Paths
TAROT_DECK_FILE = "data/tarot_deck.json"
SAVED_SPREADS_FILE = "data/saved_spreads.json"
# IMAGES_PATH - используем переменную окружения или дефолтное значение
# В Docker: /app/images/tarot, локально: ./images/tarot
# os.path.join() автоматически обрабатывает разделители путей
IMAGES_PATH = os.getenv("IMAGES_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "images", "tarot"))
logging.info(f"IMAGES_PATH установлен: {IMAGES_PATH}")
USER_DATA_FILE = "data/user_data.json"

# User preferences
DEFAULT_THEME = "light"
SHOW_CARD_IMAGES = True
