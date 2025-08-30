import os
import asyncio
import threading
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
from schedule_parser import ScheduleParser
from datetime import datetime, timedelta
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    """Запускает Flask в отдельном потоке"""
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# Настройка логирования
import logging
logging.basicConfig(level=logging.INFO)

# Получение токена бота
BOT_TOKEN = os.getenv('BOT_TOKEN', '8380069376:AAEB7UesvgxymReqmnQTIvIMNABB5_6N_gc')

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Инициализация парсера расписания
GOOGLE_DRIVE_URL = "https://drive.google.com/file/d/152JZ6IMxa07Z1oIjzv7NLhm1LhQUynzP/view?usp=sharing"
schedule_parser = ScheduleParser(GOOGLE_DRIVE_URL)

# ========================================
# КОМАНДЫ ДЛЯ РАБОТЫ С РАСПИСАНИЕМ
# ========================================

@dp.message(Command("start"))
async def send_welcome(message: Message):
    """Обработчик команды /start"""
    welcome_text = """Привет! Я бот для расписания колледжа! 🎓

📚 Доступные команды:
/start - это сообщение
/ping - проверка работоспособности
/schedule - расписание на сегодня
/schedule_tomorrow - расписание на завтра  
/schedule_week - расписание на неделю
/update_schedule - обновить расписание

👥 Ваша группа: 302Ф
🔄 Расписание обновляется автоматически"""
    
    await message.reply(welcome_text)

@dp.message(Command("ping"))
async def send_pong(message: Message):
    """Обработчик команды /ping"""
    await message.reply("pong 🏓")

@dp.message(Command("schedule"))
async def send_today_schedule(message: Message):
    """Показывает расписание на сегодня"""
    try:
        today = datetime.now().strftime('%d.%m.%Y')
        schedule = schedule_parser.get_schedule_for_date(today)
        
        if schedule:
            message_text = schedule_parser.format_schedule_message(schedule, today)
        else:
            message_text = f"📅 На {today} расписание не найдено или это выходной день."
        
        await message.reply(message_text)
    except Exception as e:
        await message.reply(f"❌ Ошибка при получении расписания: {str(e)}")

@dp.message(Command("schedule_tomorrow"))
async def send_tomorrow_schedule(message: Message):
    """Показывает расписание на завтра"""
    try:
        schedule = schedule_parser.get_schedule_for_tomorrow()
        
        if schedule:
            tomorrow = (datetime.now() + timedelta(days=1)).strftime('%d.%m.%Y')
            message_text = schedule_parser.format_schedule_message(schedule, tomorrow)
        else:
            message_text = "📅 На завтра расписание не найдено или это выходной день."
        
        await message.reply(message_text)
    except Exception as e:
        await message.reply(f"❌ Ошибка при получении расписания: {str(e)}")

@dp.message(Command("schedule_week"))
async def send_week_schedule(message: Message):
    """Показывает расписание на неделю"""
    try:
        logging.info("=== НАЧАЛО КОМАНДЫ /schedule_week ===")
        await message.reply("🔄 Получаю расписание на неделю...")
        
        logging.info("Вызываю get_schedule_for_week()...")
        schedule = schedule_parser.get_schedule_for_week()
        logging.info(f"Получено расписание: {schedule}")
        
        if schedule:
            logging.info("Расписание найдено, форматирую сообщения...")
            # Используем новую функцию для разбивки сообщений
            messages = schedule_parser.format_week_schedule_messages(schedule)
            logging.info(f"Создано {len(messages)} сообщений")
            
            # Отправляем каждое сообщение отдельно
            for i, msg in enumerate(messages):
                logging.info(f"Отправляю сообщение {i+1} из {len(messages)}")
                if i == 0:
                    await message.reply(f"{msg}\n\n📋 Часть {i+1} из {len(messages)}")
                else:
                    await message.reply(f"{msg}\n\n📋 Часть {i+1} из {len(messages)}")
                logging.info(f"Сообщение {i+1} отправлено")
        else:
            logging.info("Расписание не найдено")
            await message.reply("📅 Расписание на неделю не найдено.")
        
        logging.info("=== КОНЕЦ КОМАНДЫ /schedule_week ===")
    except Exception as e:
        logging.error(f"❌ Ошибка в /schedule_week: {str(e)}")
        await message.reply(f"❌ Ошибка при получении расписания: {str(e)}")

@dp.message(Command("update_schedule"))
async def update_schedule(message: Message):
    """Принудительно обновляет расписание"""
    try:
        await message.reply("🔄 Обновляю расписание...")
        
        if schedule_parser.update_schedule():
            await message.reply("✅ Расписание успешно обновлено!")
        else:
            await message.reply("❌ Не удалось обновить расписание. Попробуйте позже.")
    except Exception as e:
        await message.reply(f"❌ Ошибка при обновлении расписания: {str(e)}")

# ========================================
# ДОПОЛНИТЕЛЬНЫЕ КОМАНДЫ ДЛЯ РАБОТЫ С РАСПИСАНИЕМ
# ========================================
# Например:
# /schedule_group - показать расписание для конкретной группы
# /schedule_teacher - найти занятия конкретного преподавателя
# /schedule_room - найти занятия в конкретной аудитории
# ========================================

async def main():
    """Основная функция запуска бота"""
    try:
        # Запускаем бота
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"Ошибка запуска бота: {e}")

if __name__ == '__main__':
    # Запускаем Flask в отдельном потоке для Render
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Запускаем бота в основном потоке
    asyncio.run(main())
