import os
import logging
from aiogram import Bot, Dispatcher, types, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Получение токена бота
BOT_TOKEN = os.getenv('BOT_TOKEN', '8380069376:AAEB7UesvgxymReqmnQTIvIMNABB5_6N_gc')

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# ========================================
# ЗДЕСЬ БУДЕТ КОД ДЛЯ ПАРСИНГА РАСПИСАНИЯ
# ========================================
# 1. Функция для скачивания PDF с сайта колледжа
# 2. Функция для обработки PDF и извлечения данных
# 3. Функция для парсинга расписания (дата, время, предмет, преподаватель, аудитория)
# ========================================

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    """Обработчик команды /start"""
    await message.reply("Привет, я бот для расписания!")

@dp.message_handler(commands=['ping'])
async def send_pong(message: types.Message):
    """Обработчик команды /ping"""
    await message.reply("pong")

# ========================================
# ЗДЕСЬ БУДУТ ДОПОЛНИТЕЛЬНЫЕ КОМАНДЫ ДЛЯ РАБОТЫ С РАСПИСАНИЕМ
# ========================================
# Например:
# /schedule - показать расписание на сегодня
# /schedule_tomorrow - показать расписание на завтра
# /schedule_week - показать расписание на неделю
# ========================================

if __name__ == '__main__':
    # Запуск бота
    executor.start_polling(dp, skip_updates=True)
