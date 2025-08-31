import os
import logging
import asyncio
import threading
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
from schedule_parser import ScheduleParser

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Получение токена бота из переменных окружения
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    logging.error("❌ BOT_TOKEN не найден в переменных окружения!")
    exit(1)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Инициализация парсера расписания
schedule_parser = ScheduleParser("https://drive.google.com/file/d/152JZ6IMxa07Z1oIjzv7NLhm1LhQUynzP/view?usp=sharing")

# Создание клавиатуры с кнопками
def get_main_keyboard() -> InlineKeyboardMarkup:
    """Создает основную клавиатуру с кнопками"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📅 Расписание на сегодня", callback_data="schedule_today"),
            InlineKeyboardButton(text="📅 Расписание на завтра", callback_data="schedule_tomorrow")
        ],
        [
            InlineKeyboardButton(text="📅 Расписание на неделю", callback_data="schedule_week"),
            InlineKeyboardButton(text="🔄 Обновить расписание", callback_data="update_schedule")
        ],
        [
            InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help"),
            InlineKeyboardButton(text="🏓 Пинг", callback_data="ping")
        ]
    ])
    return keyboard

def get_back_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру с кнопкой 'Назад'"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
    ])
    return keyboard

# Обработчик команды /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    try:
        welcome_text = (
            "🎓 **Добро пожаловать в бот расписания группы 302 Ф!**\n\n"
            "Выберите нужную функцию:"
        )
        
        await message.answer(
            welcome_text,
            reply_markup=get_main_keyboard(),
            parse_mode="Markdown"
        )
        logging.info(f"✅ Команда /start выполнена для пользователя {message.from_user.id}")
    except Exception as e:
        logging.error(f"❌ Ошибка в команде /start: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")

# Обработчик команды /ping
@dp.message(Command("ping"))
async def cmd_ping(message: types.Message):
    """Обработчик команды /ping"""
    try:
        await message.answer("🏓 Понг! Бот работает.")
        logging.info(f"✅ Команда /ping выполнена для пользователя {message.from_user.id}")
    except Exception as e:
        logging.error(f"❌ Ошибка в команде /ping: {e}")

# Обработчик команды /schedule
@dp.message(Command("schedule"))
async def cmd_schedule(message: types.Message):
    """Обработчик команды /schedule"""
    try:
        today = datetime.now().strftime('%d.%m.%Y')
        schedule = schedule_parser.get_schedule_for_date(today)
        
        if schedule and any(lesson.get('subject') for lesson in schedule.values()):
            message_text = schedule_parser.format_schedule_message(schedule, today)
            await message.answer(message_text, reply_markup=get_back_keyboard())
        else:
            await message.answer(
                "📅 На сегодня расписания нет или произошла ошибка при загрузке.",
                reply_markup=get_back_keyboard()
            )
        logging.info(f"✅ Команда /schedule выполнена для пользователя {message.from_user.id}")
    except Exception as e:
        logging.error(f"❌ Ошибка в команде /schedule: {e}")
        await message.answer("❌ Произошла ошибка при загрузке расписания.", reply_markup=get_back_keyboard())

# Обработчик команды /schedule_tomorrow
@dp.message(Command("schedule_tomorrow"))
async def cmd_schedule_tomorrow(message: types.Message):
    """Обработчик команды /schedule_tomorrow"""
    try:
        schedule = schedule_parser.get_schedule_for_tomorrow()
        
        if schedule and any(lesson.get('subject') for lesson in schedule.values()):
            tomorrow = (datetime.now() + timedelta(days=1)).strftime('%d.%m.%Y')
            message_text = schedule_parser.format_schedule_message(schedule, tomorrow)
            await message.answer(message_text, reply_markup=get_back_keyboard())
        else:
            await message.answer(
                "📅 На завтра расписания нет или произошла ошибка при загрузке.",
                reply_markup=get_back_keyboard()
            )
        logging.info(f"✅ Команда /schedule_tomorrow выполнена для пользователя {message.from_user.id}")
    except Exception as e:
        logging.error(f"❌ Ошибка в команде /schedule_tomorrow: {e}")
        await message.answer("❌ Произошла ошибка при загрузке расписания.", reply_markup=get_back_keyboard())

# Обработчик команды /schedule_week
@dp.message(Command("schedule_week"))
async def cmd_schedule_week(message: types.Message):
    """Обработчик команды /schedule_week"""
    try:
        logging.info("=== НАЧАЛО КОМАНДЫ /schedule_week ===")
        
        schedule = schedule_parser.get_schedule_for_week()
        logging.info(f"Вызываю get_schedule_for_week()...")
        logging.info(f"Получено расписание: {schedule}")
        
        # Проверяем, есть ли реальные уроки в расписании
        has_lessons = False
        total_lessons = 0
        for day_schedule in schedule.values():
            day_lessons = len([lesson for lesson in day_schedule.values() if lesson.get('subject')])
            total_lessons += day_lessons
            if day_lessons > 0:
                has_lessons = True
        
        logging.info(f"🔍 Проверка расписания: has_lessons={has_lessons}, total_lessons={total_lessons}")
        
        if schedule and has_lessons:
            logging.info("Расписание найдено, форматирую сообщения...")
            messages = schedule_parser.format_week_schedule_messages(schedule)
            logging.info(f"Создано {len(messages)} сообщений")
            logging.info(f"Содержимое сообщений: {messages}")
            
            if messages and len(messages) > 0:
                for i, msg in enumerate(messages, 1):
                    logging.info(f"Отправляю сообщение {i} из {len(messages)}")
                    await message.answer(msg, reply_markup=get_back_keyboard())
                    logging.info(f"Сообщение {i} отправлено")
                    
                    # Небольшая задержка между сообщениями
                    if i < len(messages):
                        await asyncio.sleep(0.5)
            else:
                await message.answer(
                    "📅 Сообщения не сформированы. Возможно, проблема с форматированием.",
                    reply_markup=get_back_keyboard()
                )
        else:
            await message.answer(
                "📅 Расписание на неделю не найдено или произошла ошибка при загрузке.",
                reply_markup=get_back_keyboard()
            )
        
        logging.info("=== КОНЕЦ КОМАНДЫ /schedule_week ===")
        logging.info(f"✅ Команда /schedule_week выполнена для пользователя {message.from_user.id}")
    except Exception as e:
        logging.error(f"❌ Ошибка в команде /schedule_week: {e}")
        await message.answer("❌ Произошла ошибка при загрузке расписания.", reply_markup=get_back_keyboard())

# Обработчик команды /update_schedule
@dp.message(Command("update_schedule"))
async def cmd_update_schedule(message: types.Message):
    """Обработчик команды /update_schedule"""
    try:
        await message.answer("🔄 Обновляю расписание...")
        
        success = schedule_parser.update_schedule()
        if success:
            total_lessons = sum(len(day_schedule) for day_schedule in schedule_parser.schedule_data.values())
            has_lessons = any(lesson.get('subject') for day_schedule in schedule_parser.schedule_data.values() 
                            for lesson in day_schedule.values())
            
            if has_lessons:
                await message.answer(
                    f"✅ Расписание успешно обновлено! Теперь можете использовать команды для просмотра.\n\n"
                    f"📊 Всего найдено уроков: {total_lessons}",
                    reply_markup=get_main_keyboard()
                )
            else:
                await message.answer(
                    "⚠️ Расписание обновлено, но уроки не найдены. Возможно, произошла ошибка при парсинге.",
                    reply_markup=get_main_keyboard()
                )
        else:
            await message.answer(
                "❌ Не удалось обновить расписание. Попробуйте позже.",
                reply_markup=get_main_keyboard()
            )
        
        logging.info(f"✅ Команда /update_schedule выполнена для пользователя {message.from_user.id}")
    except Exception as e:
        logging.error(f"❌ Ошибка в команде /update_schedule: {e}")
        await message.answer("❌ Произошла ошибка при обновлении расписания.", reply_markup=get_main_keyboard())

# Обработчик callback-запросов от кнопок
@dp.callback_query()
async def process_callback(callback: types.CallbackQuery):
    """Обработчик нажатий на кнопки"""
    try:
        await callback.answer()  # Убираем "часики" у кнопки
        
        if callback.data == "schedule_today":
            today = datetime.now().strftime('%d.%m.%Y')
            schedule = schedule_parser.get_schedule_for_date(today)
            
            if schedule and any(lesson.get('subject') for lesson in schedule.values()):
                message_text = schedule_parser.format_schedule_message(schedule, today)
                await callback.message.edit_text(message_text, reply_markup=get_back_keyboard())
            else:
                await callback.message.edit_text(
                    "📅 На сегодня расписания нет или произошла ошибка при загрузке.",
                    reply_markup=get_back_keyboard()
                )
        
        elif callback.data == "schedule_tomorrow":
            schedule = schedule_parser.get_schedule_for_tomorrow()
            
            if schedule and any(lesson.get('subject') for lesson in schedule.values()):
                tomorrow = (datetime.now() + timedelta(days=1)).strftime('%d.%m.%Y')
                message_text = schedule_parser.format_schedule_message(schedule, tomorrow)
                await callback.message.edit_text(message_text, reply_markup=get_back_keyboard())
            else:
                await callback.message.edit_text(
                    "📅 На завтра расписания нет или произошла ошибка при загрузке.",
                    reply_markup=get_back_keyboard()
                )
        
        elif callback.data == "schedule_week":
            schedule = schedule_parser.get_schedule_for_week()
            
            # Проверяем, есть ли реальные уроки в расписании
            has_lessons = False
            total_lessons = 0
            for day_schedule in schedule.values():
                day_lessons = len([lesson for lesson in day_schedule.values() if lesson.get('subject')])
                total_lessons += day_lessons
                if day_lessons > 0:
                    has_lessons = True
            
            logging.info(f"🔍 Проверка расписания для callback: has_lessons={has_lessons}, total_lessons={total_lessons}")
            
            if schedule and has_lessons:
                messages = schedule_parser.format_week_schedule_messages(schedule)
                logging.info(f"Создано {len(messages)} сообщений для callback")
                logging.info(f"Содержимое сообщений: {messages}")
                
                if messages and len(messages) > 0:
                    # Отправляем первое сообщение, редактируя текущее
                    await callback.message.edit_text(messages[0], reply_markup=get_back_keyboard())
                    
                    # Отправляем остальные сообщения как новые
                    for msg in messages[1:]:
                        await callback.message.answer(msg, reply_markup=get_back_keyboard())
                        await asyncio.sleep(0.5)
                else:
                    await callback.message.edit_text(
                        "📅 Сообщения не сформированы. Возможно, проблема с форматированием.",
                        reply_markup=get_back_keyboard()
                    )
            else:
                await callback.message.edit_text(
                    "📅 Расписание на неделю не найдено или произошла ошибка при загрузке.",
                    reply_markup=get_back_keyboard()
                )
        
        elif callback.data == "update_schedule":
            await callback.message.edit_text("🔄 Обновляю расписание...")
            
            success = schedule_parser.update_schedule()
            if success:
                total_lessons = sum(len(day_schedule) for day_schedule in schedule_parser.schedule_data.values())
                has_lessons = any(lesson.get('subject') for day_schedule in schedule_parser.schedule_data.values() 
                                for lesson in day_schedule.values())
                
                if has_lessons:
                    await callback.message.edit_text(
                        f"✅ Расписание успешно обновлено! Теперь можете использовать кнопки для просмотра.\n\n"
                        f"📊 Всего найдено уроков: {total_lessons}",
                        reply_markup=get_main_keyboard()
                    )
                else:
                    await callback.message.edit_text(
                        "⚠️ Расписание обновлено, но уроки не найдены. Возможно, произошла ошибка при парсинге.",
                        reply_markup=get_main_keyboard()
                    )
            else:
                await callback.message.edit_text(
                    "❌ Не удалось обновить расписание. Попробуйте позже.",
                    reply_markup=get_main_keyboard()
                )
        
        elif callback.data == "help":
            help_text = (
                "🎓 **Бот расписания группы 302 Ф**\n\n"
                "**Доступные функции:**\n"
                "📅 Расписание на сегодня\n"
                "📅 Расписание на завтра\n"
                "📅 Расписание на неделю\n"
                "🔄 Обновить расписание\n"
                "🏓 Проверить работу бота\n\n"
                "**Команды:**\n"
                "/start - Главное меню\n"
                "/help - Эта справка\n\n"
                "**Источник данных:**\n"
                "Расписание загружается из Google Drive"
            )
            await callback.message.edit_text(help_text, reply_markup=get_back_keyboard(), parse_mode="Markdown")
        
        elif callback.data == "ping":
            await callback.message.edit_text("🏓 Понг! Бот работает.", reply_markup=get_back_keyboard())
        
        elif callback.data == "back_to_main":
            welcome_text = (
                "🎓 **Добро пожаловать в бот расписания группы 302 Ф!**\n\n"
                "Выберите нужную функцию:"
            )
            await callback.message.edit_text(welcome_text, reply_markup=get_main_keyboard(), parse_mode="Markdown")
        
        logging.info(f"✅ Callback {callback.data} обработан для пользователя {callback.from_user.id}")
        
    except Exception as e:
        logging.error(f"❌ Ошибка в обработке callback {callback.data}: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.")

# Flask приложение для Render.com
app = Flask(__name__)

@app.route('/')
def home():
    return "CRBot работает! 🤖"

def run_flask():
    """Запускает Flask в отдельном потоке"""
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))

async def main():
    """Основная функция запуска бота"""
    try:
        logging.info("🚀 Запускаю бота...")
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"❌ Ошибка запуска бота: {e}")
        raise

if __name__ == '__main__':
    try:
        flask_thread = threading.Thread(target=run_flask)
        flask_thread.daemon = True
        flask_thread.start()
        logging.info("🌐 Flask запущен в отдельном потоке")
        
        logging.info("🤖 Запускаю бота...")
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("🛑 Бот остановлен пользователем")
    except Exception as e:
        logging.error(f"❌ Критическая ошибка: {e}")
        raise
