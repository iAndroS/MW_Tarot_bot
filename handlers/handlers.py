from aiogram import Dispatcher, types, Bot
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
import os
from pathlib import Path
from settings import IMAGES_PATH, ADMIN_IDS
from utils.card_manager import CardManager
from utils.user_manager import UserManager
from utils.image_manager import ImageManager
import logging
from games.guess_card import GuessCardGame, get_try_again_keyboard
import asyncio
from utils.admin_card_editor import AdminCardEditor
from io import BytesIO
import random
from . import last_messages, bot_monitor


class SimpleMessage:
    """Класс-обёртка для безопасной работы с callback.message."""

    def __init__(self, callback):
        self.chat = callback.message.chat if callback.message else None
        self.message_id = callback.message.message_id if callback.message else None
        self.from_user = callback.from_user if callback.from_user else None
        self.bot = callback.bot if callback.bot else None
        logging.debug(f"SimpleMessage created: chat={self.chat}, message_id={self.message_id}, user={self.from_user}")

    async def answer(self, text: str, **kwargs):
        """Отправляет сообщение в чат через bot."""
        if not self.bot:
            logging.error("SimpleMessage.answer: bot is None")
            raise RuntimeError("Bot instance is not available")
        if not self.chat:
            logging.error("SimpleMessage.answer: chat is None")
            raise RuntimeError("Chat is not available")
        
        logging.debug(f"SimpleMessage.answer: sending message to chat {self.chat.id}")
        return await self.bot.send_message(self.chat.id, text=text, **kwargs)

    async def answer_photo(self, photo, **kwargs):
        """Отправляет фото в чат через bot."""
        if not self.bot:
            logging.error("SimpleMessage.answer_photo: bot is None")
            raise RuntimeError("Bot instance is not available")
        if not self.chat:
            logging.error("SimpleMessage.answer_photo: chat is None")
            raise RuntimeError("Chat is not available")
        
        logging.debug(f"SimpleMessage.answer_photo: sending photo to chat {self.chat.id}")
        return await self.bot.send_photo(self.chat.id, photo=photo, **kwargs)


# Хранение текущей информации пользователя
user_data = {}
user_manager = UserManager()
image_manager = ImageManager()
guess_game = GuessCardGame()

# Путь к изображениям
IMAGES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images", "tarot")

# Инициализация редактора карт
admin_card_editor = AdminCardEditor()

# Словарь для хранения состояния редактирования
edit_states = {}

# Глобальная переменная для хранения монитора
bot_monitor = None

def set_monitor(monitor):
    """Установка глобального монитора."""
    global bot_monitor
    bot_monitor = monitor

async def delete_previous_messages(chat_id: int, user_message: types.Message, new_message_id: int = None):
    """Удаляет предыдущие сообщения в чате после отправки нового."""
    if chat_id in last_messages:
        await asyncio.sleep(1.5)  # Задержка перед удалением
        
        try:
            # Удаляем предыдущее сообщение бота
            if "bot" in last_messages[chat_id]:
                await user_message.bot.delete_message(chat_id, last_messages[chat_id]["bot"])
        except Exception as e:
            logging.warning(f"Не удалось удалить сообщение бота: {e}")
        
        try:
            # Удаляем предыдущее сообщение пользователя
            if "user" in last_messages[chat_id]:
                await user_message.bot.delete_message(chat_id, last_messages[chat_id]["user"])
        except Exception as e:
            logging.warning(f"Не удалось удалить сообщение пользователя: {e}")

async def send_message_and_save_id(message: types.Message, text: str, **kwargs):
    """Отправляет сообщение и сохраняет его ID, удаляя предыдущие сообщения."""
    chat_id = message.chat.id
    logging.debug(f"send_message_and_save_id: chat_id={chat_id}, message type={type(message).__name__}")
    
    # Отправляем новое сообщение
    try:
        if hasattr(message, 'answer'):
            sent_message = await message.answer(text, **kwargs)
        else:
            logging.error(f"message object has no 'answer' method: {type(message)}")
            raise RuntimeError(f"Message object has no answer method: {type(message)}")
    except Exception as e:
        logging.error(f"Error in send_message_and_save_id: {e}")
        raise
    
    # Удаляем предыдущие сообщения
    await delete_previous_messages(chat_id, message)
    
    # Сохраняем ID нового сообщения
    last_messages[chat_id] = {
        "user": message.message_id,
        "bot": sent_message.message_id
    }
    
    return sent_message

def get_main_keyboard(user_id: int | None = None):
    # Формируем клавиатуру для aiogram 3.x
    keyboard_rows = [
        [KeyboardButton(text="💰 Финансы"), KeyboardButton(text="❤️ Отношения")],
        [KeyboardButton(text="🌅 Карта дня"), KeyboardButton(text="💼 Карьера")],
        [KeyboardButton(text="🌙 На месяц"), KeyboardButton(text="🌟 На неделю")],
        [KeyboardButton(text="💫 Подсказка"), KeyboardButton(text="⚙️ Настройки")],
        [KeyboardButton(text="🎲 Угадай карту")],
    ]

    # Логируем только факт наличия прав админа (без конкретных ID)
    is_admin = user_id in ADMIN_IDS
    logging.info("Main menu for user %s. Admin=%s", user_id, is_admin)

    if user_id in ADMIN_IDS:
        keyboard_rows.append([KeyboardButton(text="👑 Админ-панель")])
    
    # Проверяем наличие файлов обратной связи
    current_dir = Path(__file__).parent.parent  # Поднимаемся на уровень выше
    feedback_path = current_dir / "utils" / "feedback.py"
    handlers_path = current_dir / "handlers" / "feedback_handlers.py"
    
    logging.info(f"Проверка файлов обратной связи:")
    logging.info(f"feedback_path: {feedback_path} (exists: {feedback_path.exists()})")
    logging.info(f"handlers_path: {handlers_path} (exists: {handlers_path.exists()})")
    
    if feedback_path.exists() and handlers_path.exists():
        logging.info("Добавляю кнопку обратной связи")
        keyboard_rows.append([KeyboardButton(text="📝 Обратная связь")])
    else:
        logging.info("Кнопка обратной связи не добавлена: файлы не найдены")
    
    return ReplyKeyboardMarkup(keyboard=keyboard_rows, resize_keyboard=True)

async def delete_user_message(message: types.Message):
    """Немедленно удаляет сообщение пользователя."""
    try:
        await message.delete()
    except Exception as e:
        logging.warning(f"Не удалось удалить сообщение пользователя: {e}")

async def send_photo_and_save_id(message: types.Message, photo, **kwargs):
    """Отправляет фото и сохраняет его ID, удаляя предыдущие сообщения."""
    chat_id = message.chat.id
    
    # Отправляем новое сообщение с фото
    sent_message = await message.answer_photo(photo=photo, **kwargs)
    
    # Удаляем предыдущие сообщения
    await delete_previous_messages(chat_id, message)
    
    # Сохраняем ID нового сообщения
    last_messages[chat_id] = {
        "user": message.message_id,
        "bot": sent_message.message_id
    }
    
    return sent_message

async def cmd_start(message: types.Message):
    user_id = str(message.from_user.id)
    
    # Создаем красивое приветственное сообщение
    welcome_text = (
        "✨ *Добро пожаловать в Мистический Мир Таро!* ✨\n\n"
        "🔮 Я - ваш личный проводник в мир древних тайн и предсказаний. "
        "Позвольте мне приоткрыть завесу будущего и помочь найти ответы на ваши вопросы.\n\n"
        "🌟 *Мои возможности:*\n\n"
        "💰 *Финансы*\n└ Раскройте секреты вашего финансового процветания\n\n"
        "❤️ *Отношения*\n└ Найдите путь к гармонии в личной жизни\n\n"
        "💼 *Карьера*\n└ Откройте новые профессиональные горизонты\n\n"
        "🌅 *Карта дня*\n└ Узнайте, какие энергии окружают вас сегодня\n\n"
        "🌟 *На неделю*\n└ Загляните в ближайшее будущее\n\n"
        "🌙 *На месяц*\n└ Раскройте перспективы грядущего месяца\n\n"
        "✨ *Как это работает:*\n"
        "🎴 Для каждого расклада я выберу три особенные карты.\n"
        "🌟 Прислушайтесь к своей интуиции при выборе карты.\n"
        "📜 После расклада вы сможете узнать древнюю историю выбранной карты.\n\n"
        "🌌 *Готовы начать магическое путешествие?*\n"
        "└ Выберите интересующую вас сферу жизни ⬇️"
    )

    # Добавляем информацию о предыдущем раскладе, если он есть
    if CardManager.has_saved_spread(user_id):
        welcome_text += "\n\n🎴 У вас есть сохранённый расклад. Хотите его посмотреть? (Напишите 'да' или выберите новую тему)"
    
    # Всегда отправляем приветственное сообщение
    await send_message_and_save_id(message, welcome_text, reply_markup=get_main_keyboard(message.from_user.id), parse_mode="Markdown")

async def handle_theme(message: types.Message):
    user_id = message.from_user.id
    # Убираем эмодзи из темы
    theme = message.text.split(' ', 1)[1] if ' ' in message.text else message.text
    
    if not await user_manager.can_make_spread(user_id):
        await message.reply(
            "⚠️ *Лимит раскладов на сегодня достигнут*\n\n"
            "🌙 Карты Таро нуждаются в отдыхе, чтобы восстановить свою магическую силу.\n"
            "✨ Пожалуйста, возвращайтесь завтра для новых предсказаний.\n\n"
            "💫 _Если вам срочно нужен совет, обратитесь к администратору._",
            parse_mode="Markdown"
        )
        return
    
    # Преобразуем названия тем для соответствия с tarot_deck.json
    theme_mapping = {
        "💰 Финансы": "Финансы",
        "❤️ Отношения": "Отношения",
        "🌅 Карта дня": "Карта на сегодня",
        "💼 Карьера": "Карьера",
        "🌙 На месяц": "Карта на месяц",
        "🌟 На неделю": "Карта на неделю",
        "💫 Подсказка": "Подсказка"
    }
    
    actual_theme = theme_mapping.get(message.text, message.text)
    
    card_manager = CardManager()
    cards = card_manager.generate_spread()
    user_data[str(user_id)] = {"theme": actual_theme, "cards": cards}
    await user_manager.increment_spreads(user_id)
    await card_manager.save_spread(str(user_id), actual_theme, cards)
    
    cards_keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🎴"), KeyboardButton(text="🎴"), KeyboardButton(text="🎴")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await send_message_and_save_id(
        message,
        "✨ *Карты Таро разложены перед вами* ✨\n\n"
        "🔮 Я разложила три карты для вашего вопроса.\n"
        "💫 Прислушайтесь к своей интуиции и выберите одну из карт...\n\n"
        "🌟 _Каждая карта несёт своё уникальное послание._",
        reply_markup=cards_keyboard,
        parse_mode="Markdown"
    )

def get_card_image_name(card_name: str) -> str:
    """Преобразует название карты в имя файла изображения."""
    # Убираем "The " из названия
    name = card_name.replace("The ", "")
    
    # Разбиваем название на части
    parts = name.split()
    
    # Соединяем части с подчеркиванием
    name = "_".join(parts)
    
    # Логируем результат
    logging.info(f"Оригинальное название карты: {card_name}")
    logging.info(f"Сформированное имя файла: {name}")
    logging.info(f"Полный путь к файлу: {os.path.join(IMAGES_DIR, f'{name}.jpg')}")
    
    return name

async def handle_card_choice(message: types.Message):
    user_id = str(message.from_user.id)
    if user_id not in user_data:
        await message.reply(
            "✨ *Магическая связь прервалась*\n\n"
            "🌙 Пожалуйста, начните новый расклад, выбрав интересующую вас сферу.",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(message.from_user.id)
        )
        return
    
    # Определяем индекс выбранной карты по порядку нажатия
    cards = user_data[user_id]["cards"]
    theme = user_data[user_id]["theme"]
    
    # Получаем индекс карты из сообщения
    if "current_card_index" not in user_data[user_id]:
        user_data[user_id]["current_card_index"] = 0
    card_index = user_data[user_id]["current_card_index"]
    user_data[user_id]["current_card_index"] = (card_index + 1) % 3
    
    card_name = cards[card_index]
    card_manager = CardManager()
    card_info = await card_manager.get_card_info(card_name)
    user_data[user_id]["current_card"] = card_info
    
    # Создаем клавиатуру для дополнительных действий
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🔮 Новый расклад")]],
        resize_keyboard=True
    )
    
    # Случайные магические окончания
    endings = [
        "🎴 *Карты Таро раскрыли свою тайну...* Прислушайтесь к их мудрости",
        "🔮 *Древние символы указали ваш путь...* Следуйте их знакам",
        "🎴 *Мистические арканы говорят с вами...* Доверьтесь их силе",
        "🔮 *Карты открыли завесу будущего...* Познайте их откровения",
        "🎴 *Таро делится своей мудростью...* Примите их послание",
        "🎴 *Древние арканы раскрыли свои тайны...* Познайте их истину"
    ]
    
    # Формируем сообщение с предсказанием
    # Используем get() для безопасного доступа к полям карты
    card_meaning = card_info.get(theme)
    if not card_meaning:
        # Fallback: если тема не найдена, используем "Карта на сегодня" или "meaning"
        card_meaning = card_info.get('Карта на сегодня') or card_info.get('meaning',
            'Карта не может дать точный ответ на этот вопрос сегодня. '
            'Прислушайтесь к своей интуиции...')
        logging.warning(f"Theme '{theme}' not found for card {card_info.get('ru', 'Unknown')}, using fallback")
    
    message_text = (
        f"✨ *Ваше предсказание для сферы {theme}* ✨\n\n"
        f"🎴 *{card_info['ru']}*\n\n"
        f"📜 *Значение карты:*\n└ _{card_meaning}_\n\n"
        f"{random.choice(endings)}"
    )
    
    # Отправляем сообщение с картой
    user = await user_manager.get_user(int(user_id))
    if user["show_images"]:
        try:
            # Получаем оптимизированное изображение через ImageManager
            image_bytes = await image_manager.get_image(card_info['en'])
            if image_bytes:
                photo = BufferedInputFile(image_bytes, filename=f"{card_info['en']}.jpg")
                await send_photo_and_save_id(
                    message,
                    photo=photo,
                    caption=message_text,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
            else:
                await send_message_and_save_id(
                    message,
                    message_text + "\n\n⚠️ _Изображение карты временно недоступно_",
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
        except Exception as e:
            logging.error(f"Ошибка при отправке изображения: {e}")
            await send_message_and_save_id(
                message,
                message_text + "\n\n⚠️ _Не удалось отправить изображение карты_",
                parse_mode="Markdown",
                reply_markup=keyboard
            )
    else:
        await send_message_and_save_id(
            message,
            message_text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )

async def handle_history_request(message: types.Message):
    user_id = str(message.from_user.id)
    if user_id not in user_data or "current_card" not in user_data[user_id]:
        await message.reply(
            "✨ *Магическая связь с картой потеряна*\n\n"
            "🌙 Давайте начнем новое гадание, чтобы восстановить связь с картами Таро.",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(message.from_user.id)
        )
        return

    card_info = user_data[user_id]["current_card"]
    history = card_info.get("history", "История этой карты окутана тайной...")
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🔮 Новый расклад")]],
        resize_keyboard=True
    )
    
    history_text = (
        f"📜 *История карты {card_info['ru']}* 📜\n\n"
        f"✨ _{history}_\n\n"
        "🌟 *Мудрость веков:*\n"
        "└ Каждая карта Таро хранит в себе древние знания и силу...\n\n"
        "🔮 Хотите сделать новый расклад?"
    )
    
    user = await user_manager.get_user(int(user_id))
    if user["show_images"]:
        try:
            # Получаем оптимизированное изображение через ImageManager
            image_bytes = await image_manager.get_image(card_info['en'])
            if image_bytes:
                photo = BufferedInputFile(image_bytes, filename=f"{card_info['en']}.jpg")
                await send_photo_and_save_id(
                    message,
                    photo=photo,
                    caption=history_text,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
                return
        except Exception as e:
            logging.error(f"Ошибка при отправке изображения: {e}")
    
    await send_message_and_save_id(
        message,
        history_text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )

async def handle_return_to_themes(message: types.Message):
    """Обработчик для возврата к выбору темы гадания."""
    await send_message_and_save_id(
        message,
        "✨ *Выберите сферу для нового предсказания* ✨\n\n"
        "🌟 Карты Таро готовы раскрыть перед вами новые тайны...\n"
        "└ Какая сфера жизни интересует вас сейчас?",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard(message.from_user.id)
    )

async def settings_menu(message: types.Message):
    """Показывает меню настроек."""
    user = await user_manager.get_user(message.from_user.id)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{'🌞' if user['theme'] == 'light' else '🌙'} Тема: {'Светлая' if user['theme'] == 'light' else 'Тёмная'}",
                callback_data="toggle_theme"
            )],
            [InlineKeyboardButton(
                text="🔄 Сбросить настройки",
                callback_data="reset_settings"
            )]
        ]
    )
    
    await message.reply(
        "⚙️ *Настройки*\n\n"
        "Здесь вы можете настроить бота под себя:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

async def handle_settings_callback(callback: types.CallbackQuery):
    """Обработчик callback-запросов для меню настроек."""
    user_id = callback.from_user.id
    user = await user_manager.get_user(user_id)
    logging.info(f"Текущие настройки пользователя {user_id}: {user}")
    
    if callback.data == "toggle_theme":
        new_theme = "dark" if user["theme"] == "light" else "light"
        await user_manager.update_preferences(user_id, theme=new_theme)
        await callback.answer(
            f"✨ Тема изменена на {'тёмную 🌙' if new_theme == 'dark' else 'светлую 🌞'}"
        )
    
    elif callback.data == "reset_settings":
        await user_manager.reset_preferences(user_id)
        await callback.answer("🔄 Настройки сброшены к значениям по умолчанию")
    
    # Получаем обновленные настройки
    user = await user_manager.get_user(user_id)
    logging.info(f"Обновленные настройки пользователя {user_id}: {user}")
    
    # Формируем сообщение в зависимости от темы
    if user["theme"] == "light":
        theme_emoji = "🌞"
        theme_text = "Светлая"
        message_text = (
            "⚙️ *Настройки*\n\n"
            "🎨 Текущая тема: Светлая 🌞\n\n"
            "☀️ Используйте кнопки ниже для изменения настроек:"
        )
    else:
        theme_emoji = "🌙"
        theme_text = "Тёмная"
        message_text = (
            "⚙️ *Настройки*\n\n"
            "🎨 Текущая тема: Тёмная 🌙\n\n"
            "🌠 Используйте кнопки ниже для изменения настроек:"
        )
    
    # Обновляем клавиатуру
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{theme_emoji} Тема: {theme_text}",
                callback_data="toggle_theme"
            )],
            [InlineKeyboardButton(
                text="🔄 Сбросить настройки",
                callback_data="reset_settings"
            )]
        ]
    )
    
    try:
        await callback.message.edit_text(
            message_text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    except TelegramBadRequest:
        logging.warning("Сообщение не изменилось, пропускаем обновление")
        pass

async def send_daily_prediction(bot: Bot):
    subscribers = await user_manager.get_daily_prediction_subscribers()
    card_manager = CardManager()
    
    for user_id in subscribers:
        try:
            user = await user_manager.get_user(user_id)
            card = await card_manager.get_random_card()
            
            message_text = (
                "✨ *Ваше Предсказание на Сегодня* ✨\n\n"
                f"🎴 Карта дня: *{card['ru']}*\n\n"
                f"📜 Послание карты:\n└ _{card['Карта на сегодня']}_\n\n"
                "🌟 Пусть этот день принесёт вам мудрость и озарение!\n"
                "└ _Ваш мистический проводник_"
            )
            
            # Удаляем предыдущее сообщение бота, если оно есть
            if user_id in last_messages and "bot" in last_messages[user_id]:
                try:
                    await bot.delete_message(user_id, last_messages[user_id]["bot"])
                except Exception as e:
                    logging.warning(f"Не удалось удалить предыдущее предсказание: {e}")
            
            # Отправляем новое предсказание
            if user["show_images"]:
                image_name = get_card_image_name(card['en'])
                image_path = os.path.join(IMAGES_DIR, f"{image_name}.jpg")
                if os.path.exists(image_path):
                    sent_message = await bot.send_photo(
                        user_id,
                        photo=FSInputFile(image_path),
                        caption=message_text,
                        parse_mode="Markdown"
                    )
                else:
                    sent_message = await bot.send_message(
                        user_id,
                        message_text,
                        parse_mode="Markdown"
                    )
            else:
                sent_message = await bot.send_message(
                    user_id,
                    message_text,
                    parse_mode="Markdown"
                )
            
            # Сохраняем только ID сообщения бота
            last_messages[user_id] = {
                "bot": sent_message.message_id
            }
                
        except Exception as e:
            logging.error(f"Ошибка при отправке дневного предсказания пользователю {user_id}: {e}")
            continue

async def handle_guess_card_game(message: types.Message):
    """Начинает новую игру 'Угадай карту'."""
    target_card, options, keyboard = guess_game.start_new_game(message.from_user.id)
    
    # Логируем информацию о карте
    logging.info(f"Загаданная карта: {target_card}")
    
    # Формируем сообщение
    game_text = (
        "🎲 *Игра: Угадай карту* 🎲\n\n"
        f"✨ Я загадала карту *{target_card['ru']}*\n\n"
        "🎴 Перед вами 5 перевёрнутых карт\n"
        "└ Найдите загаданную карту среди них!\n\n"
        "💫 Прислушайтесь к своей интуиции..."
    )
    
    try:
        # Получаем оптимизированное изображение через ImageManager
        image_bytes = await image_manager.get_image(target_card['en'])
        if image_bytes:
            photo = BufferedInputFile(image_bytes, filename=f"{target_card['en']}.jpg")
            await send_photo_and_save_id(
                message,
                photo=photo,
                caption=game_text,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        else:
            await send_message_and_save_id(
                message,
                game_text + "\n\n⚠️ _Изображение карты временно недоступно_",
                parse_mode="Markdown",
                reply_markup=keyboard
            )
    except Exception as e:
        logging.error(f"Ошибка при отправке изображения: {e}")
        await send_message_and_save_id(
            message,
            game_text + "\n\n⚠️ _Не удалось отправить изображение карты_",
            parse_mode="Markdown",
            reply_markup=keyboard
        )

async def handle_guess_callback(callback: types.CallbackQuery):
    """Обрабатывает выбор карты в игре."""
    logging.info(f"handle_guess_callback: user={callback.from_user.id}, data={callback.data}")
    
    # Получаем индекс выбранной карты
    data_parts = callback.data.split('_')
    selected_index = int(data_parts[1])
    
    # Проверяем угадал ли пользователь
    is_correct, target_card, selected_card = guess_game.check_guess(callback.from_user.id, selected_index)
    logging.info(f"handle_guess_callback: is_correct={is_correct}, target={target_card['ru'] if target_card else None}")

    # Создаем объект message из callback.message
    message = SimpleMessage(callback)

    if is_correct:
        success_text = (
            "🎉 *Поздравляем! Вы угадали!* 🎉\n\n"
            "✨ Ваша интуиция привела вас к правильной карте!\n\n"
            "🌟 История этой карты:\n"
            f"└ _{target_card.get('history', 'История этой карты окутана тайной...')}_\n\n"
            "💫 Продолжайте развивать свой дар..."
        )
        
        # Отправляем новое сообщение
        await send_message_and_save_id(
            message,
            success_text,
            parse_mode="Markdown",
            reply_markup=get_try_again_keyboard()
        )
    else:
        fail_text = (
            "✨ *К сожалению, это не та карта* ✨\n\n"
            f"🎴 Вы выбрали: *{selected_card['ru']}*\n"
            f"└ _{selected_card.get('history', 'История этой карты окутана тайной...')}_\n\n"
            "💫 Не отчаивайтесь, каждая попытка приближает вас\n"
            "к лучшему пониманию карт Таро...\n"
            "└ Попробуете еще раз?"
        )
        
        try:
            # Получаем оптимизированное изображение через ImageManager
            image_bytes = await image_manager.get_image(selected_card['en'])
            if image_bytes:
                photo = BufferedInputFile(image_bytes, filename=f"{selected_card['en']}.jpg")
                await send_photo_and_save_id(
                    message,
                    photo=photo,
                    caption=fail_text,
                    parse_mode="Markdown",
                    reply_markup=get_try_again_keyboard()
                )
            else:
                await send_message_and_save_id(
                    message,
                    fail_text,
                    parse_mode="Markdown",
                    reply_markup=get_try_again_keyboard()
                )
        except Exception as e:
            logging.error(f"Ошибка при отправке изображения: {e}")
            await send_message_and_save_id(
                message,
                fail_text,
                parse_mode="Markdown",
                reply_markup=get_try_again_keyboard()
            )

async def admin_menu(message: types.Message):
    """Показывает админское меню."""
    if message.from_user.id not in ADMIN_IDS:
        return
        
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Редактировать карту", callback_data="edit_card_start")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton(text="🔙 Вернуться", callback_data="return_to_main")]
        ]
    )
    
    await send_message_and_save_id(
        message,
        "👑 *Админ-панель*\n\n"
        "Выберите действие:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

async def handle_edit_card_start(callback: types.CallbackQuery):
    """Начинает процесс редактирования карты."""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️ Доступ запрещен")
        return
        
    # Получаем список всех карт
    cards = admin_card_editor.get_all_cards()
    
    # Создаем клавиатуру с картами (по 2 в ряд)
    keyboard_rows = []
    for i in range(0, len(cards), 2):
        row = []
        for card in cards[i:i+2]:
            row.append(InlineKeyboardButton(text=card, callback_data=f"select_card_{card}"))
        keyboard_rows.append(row)
    
    # Добавляем кнопку возврата
    keyboard_rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_menu")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    
    await callback.message.edit_text(
        "🎴 *Выберите карту для редактирования:*",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

async def handle_card_selection(callback: types.CallbackQuery):
    """Обрабатывает выбор карты для редактирования."""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️ Доступ запрещен")
        return
        
    card_name = callback.data.replace("select_card_", "")
    card_info = admin_card_editor.get_card_info(card_name)
    
    if not card_info:
        await callback.answer("❌ Карта не найдена")
        return
        
    # Сохраняем выбранную карту в состоянии
    edit_states[callback.from_user.id] = {"card": card_name}
    
    # Создаем клавиатуру с полями для редактирования
    keyboard_rows = []
    for field in admin_card_editor.get_all_fields():
        keyboard_rows.append([InlineKeyboardButton(text=f"📝 {field}", callback_data=f"edit_field_{field}")])
    keyboard_rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="edit_card_start")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    
    # Формируем текст с текущими значениями
    text = f"🎴 *Карта: {card_name}*\n\n"
    for field in admin_card_editor.get_all_fields():
        text += f"*{field}:*\n└ _{card_info.get(field, 'Не задано')}_\n\n"
    text += "Выберите поле для редактирования:"
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )

async def handle_field_selection(callback: types.CallbackQuery):
    """Обрабатывает выбор поля для редактирования."""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️ Доступ запрещен")
        return
        
    field = callback.data.replace("edit_field_", "")
    user_state = edit_states.get(callback.from_user.id)
    
    if not user_state:
        await callback.answer("❌ Ошибка состояния")
        return
        
    # Сохраняем выбранное поле в состоянии
    user_state["field"] = field
    edit_states[callback.from_user.id] = user_state
    
    await callback.message.edit_text(
        f"✏️ *Редактирование карты {user_state['card']}*\n\n"
        f"Поле: *{field}*\n\n"
        "Отправьте новое значение для этого поля.\n"
        "Для отмены нажмите кнопку ниже.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data=f"select_card_{user_state['card']}")]]
        )
    )
    
    # Устанавливаем состояние ожидания нового значения
    user_state["waiting_for_value"] = True

async def handle_new_value(message: types.Message):
    """Обрабатывает новое значение поля."""
    if message.from_user.id not in ADMIN_IDS:
        return
        
    user_state = edit_states.get(message.from_user.id)
    if not user_state or not user_state.get("waiting_for_value"):
        return
        
    # Обновляем значение в JSON
    success = admin_card_editor.update_card(
        user_state["card"],
        user_state["field"],
        message.text
    )
    
    if success:
        await message.reply(
            "✅ Значение успешно обновлено!\n\n"
            "Выберите следующее действие:",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="📝 Продолжить редактирование", callback_data=f"select_card_{user_state['card']}")],
                    [InlineKeyboardButton(text="🔙 Вернуться в админ-меню", callback_data="admin_menu")]
                ]
            )
        )
    else:
        await message.reply(
            "❌ Произошла ошибка при обновлении значения.\n"
            "Попробуйте еще раз или вернитесь в меню:",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="🔙 Вернуться", callback_data=f"select_card_{user_state['card']}")]]
            )
        )
    
    # Очищаем состояние ожидания
    user_state["waiting_for_value"] = False
    edit_states[message.from_user.id] = user_state

async def handle_admin_stats(callback: types.CallbackQuery):
    """Показывает статистику использования бота."""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️ Доступ запрещен")
        return

    await callback.answer()

    stats = await user_manager.db.get_stats()
    total_users = stats.get("total_users", 0)
    daily_subscribers = stats.get("daily_subscribers", 0)
    
    stats_text = (
        "📊 *Статистика бота*\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"🔔 Подписчиков на рассылку: {daily_subscribers}\n"
        "└ _(Будет дополняться)_"
    )
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="admin_menu")]]
    )
    
    await callback.message.edit_text(
        stats_text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )

async def handle_return_to_main(callback: types.CallbackQuery):
    """Обработчик возврата в главное меню из админ-панели."""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️ Доступ запрещен")
        return

    await callback.answer()

    # Создаем объект message для использования в send_message_and_save_id
    message = SimpleMessage(callback)

    # Удаляем сообщение с админ-меню
    try:
        await callback.message.delete()
    except Exception as e:
        logging.warning(f"Не удалось удалить сообщение админ-меню: {e}")
    
    # Отправляем новое сообщение с главным меню
    await send_message_and_save_id(
        message,
        "✨ *Добро пожаловать в главное меню!*\n\n"
        "Выберите действие из меню ниже:",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard(message.from_user.id)
    )

async def handle_admin_menu_callback(callback: types.CallbackQuery):
    """Обработчик возврата в админ-меню."""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️ Доступ запрещен")
        return
        
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Редактировать карту", callback_data="edit_card_start")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton(text="🔙 Вернуться", callback_data="return_to_main")]
        ]
    )
    
    await callback.message.edit_text(
        "👑 *Админ-панель*\n\n"
        "Выберите действие:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

async def send_card_image(message: types.Message, card_info: dict):
    """Отправка изображения карты."""
    try:
        image_data = await image_manager.get_image(card_info['en'])
        if image_data:
            photo = BufferedInputFile(image_data, filename=f"{card_info['en']}.jpg")
            await message.answer_photo(
                photo=photo,
                caption=f"🎴 {card_info['ru']}\n\n{card_info['meaning']}"
            )
        else:
            await message.answer(f"Извините, не удалось загрузить изображение карты {card_info['ru']}")
    except Exception as e:
        logging.error(f"Ошибка при отправке изображения карты: {e}")
        await message.answer("Извините, произошла ошибка при отправке изображения карты")

async def cmd_stats(message: types.Message):
    """Получение статистики бота."""
    if message.from_user.id not in ADMIN_IDS:
        return
        
    if not bot_monitor:
        await message.reply("❌ Ошибка: монитор не инициализирован")
        return
        
    try:
        report = bot_monitor.get_stats_report()
        await message.reply(
            f"📊 *Статистика бота*\n\n{report}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"Ошибка при получении статистики: {e}")
        await message.reply("❌ Произошла ошибка при получении статистики")

async def handle_try_again(callback: types.CallbackQuery):
    """Обработчик кнопки 'Попробовать еще раз'."""
    # Создаем объект message из callback.message
    message = SimpleMessage(callback)

    # Запускаем новую игру
    await handle_guess_card_game(message)

async def handle_return_to_menu(callback: types.CallbackQuery):
    """Обработчик кнопки 'Вернуться в меню'."""
    # Создаем объект message из callback.message
    message = SimpleMessage(callback)

    # Возвращаемся в главное меню
    await send_message_and_save_id(
        message,
        "✨ *Добро пожаловать в главное меню* ✨\n\n"
        "🌟 Выберите действие, которое вас интересует:",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard(message.from_user.id)
    )

async def show_main_menu(message: types.Message):
    """Показывает главное меню по команде пользователя."""
    await send_message_and_save_id(
        message,
        "✨ *Добро пожаловать в главное меню* ✨\n\n"
        "🌟 Выберите действие, которое вас интересует:",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard(message.from_user.id)
    )

def register_handlers(dp: Dispatcher, log_decorator=None):
    """Регистрация всех обработчиков."""
    if log_decorator is None:
        log_decorator = lambda x: x
    
    # Основные команды
    dp.message.register(log_decorator(cmd_start), Command(commands=['start']))
    dp.message.register(log_decorator(show_main_menu), Command(commands=['menu']))
    dp.message.register(log_decorator(admin_menu), lambda msg: msg.text == "👑 Админ-панель")
    dp.message.register(log_decorator(settings_menu), lambda msg: msg.text == "⚙️ Настройки")
    dp.message.register(log_decorator(handle_theme), 
                              lambda message: any(message.text.endswith(theme) for theme in 
                              ["💰 Финансы", "❤️ Отношения", "🌅 Карта дня", "💼 Карьера", 
                               "🌙 На месяц", "🌟 На неделю", "💫 Подсказка"]))
    dp.message.register(log_decorator(handle_card_choice), 
                              lambda message: message.text == "🎴")
    dp.message.register(log_decorator(handle_history_request), lambda message: message.text == "📜 История карты")
    dp.message.register(log_decorator(handle_return_to_themes), lambda message: message.text in ["🔮 Новый расклад", "🔮 Вернуться к гаданию"])
    dp.callback_query.register(log_decorator(handle_settings_callback), lambda c: c.data in ["toggle_theme", "reset_settings"])
    
    # Обработчики для игры
    dp.message.register(log_decorator(handle_guess_card_game), lambda m: m.text == "🎲 Угадай карту")
    dp.callback_query.register(log_decorator(handle_guess_callback), lambda c: c.data.startswith("guess_"))
    dp.callback_query.register(log_decorator(handle_try_again), lambda c: c.data == "try_again")
    dp.callback_query.register(log_decorator(handle_return_to_menu), lambda c: c.data == "return_to_menu")
    
    # Админские хендлеры
    dp.message.register(log_decorator(admin_menu), Command(commands=['admin']))
    dp.callback_query.register(log_decorator(handle_edit_card_start), lambda c: c.data == "edit_card_start")
    dp.callback_query.register(log_decorator(handle_card_selection), lambda c: c.data.startswith("select_card_"))
    dp.callback_query.register(log_decorator(handle_field_selection), lambda c: c.data.startswith("edit_field_"))
    dp.callback_query.register(log_decorator(handle_admin_stats), lambda c: c.data == "admin_stats")
    dp.callback_query.register(log_decorator(handle_admin_menu_callback), lambda c: c.data == "admin_menu")
    dp.callback_query.register(log_decorator(handle_return_to_main), lambda c: c.data == "return_to_main")
    
    # Регистрируем хендлер статистики
    # Важно: в aiogram 3.x фильтры применяются в порядке передачи
    # Сначала проверяем права админа, затем парсим команду
    dp.message.register(
        log_decorator(cmd_stats),
        lambda message: message.from_user.id in ADMIN_IDS,
        Command(commands=['stats'])
    )
