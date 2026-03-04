import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

if not BOT_TOKEN:
	raise RuntimeError("BOT_TOKEN is not set. Add it to .env or environment variables.")

# Пути к файлам данных
TAROT_DECK_FILE = "data/tarot_deck.json"
SAVED_SPREADS_FILE = "data/saved_spreads.json"

# Пути к изображениям
IMAGES_PATH = "/app/images/tarot/" 