import os
import logging
from datetime import datetime, timedelta
import json
from typing import Dict, List, Optional
import asyncio
import threading
from flask import Flask, request, jsonify

# Импорты для aiogram
try:
    from aiogram import Bot, Dispatcher, types
    from aiogram.contrib.fsm_storage.memory import MemoryStorage
    from aiogram.dispatcher import FSMContext
    from aiogram.dispatcher.filters.state import State, StatesGroup
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.utils import executor
except ImportError:
    logging.error("❌ aiogram не установлен. Установите: pip install aiogram")
    exit(1)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация Flask для Render.com
app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"status": "Bot is running", "timestamp": datetime.now().isoformat()})

def run_flask():
    """Запускает Flask в отдельном потоке"""
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# Состояния для FSM
class ScheduleStates(StatesGroup):
    waiting_for_schedule_type = State()
    waiting_for_study_schedule = State()
    waiting_for_work_schedule = State()
    waiting_for_voice_input = State()

class ScheduleManager:
    """Менеджер расписания пользователя"""
    
    def __init__(self):
        self.schedules = {}  # user_id -> schedule_data
        self.load_schedules()
    
    def load_schedules(self):
        """Загружает расписания из файла"""
        try:
            if os.path.exists('schedules.json'):
                with open('schedules.json', 'r', encoding='utf-8') as f:
                    self.schedules = json.load(f)
                logger.info(f"📂 Загружено {len(self.schedules)} расписаний")
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки расписаний: {e}")
            self.schedules = {}
    
    def save_schedules(self):
        """Сохраняет расписания в файл"""
        try:
            with open('schedules.json', 'w', encoding='utf-8') as f:
                json.dump(self.schedules, f, ensure_ascii=False, indent=2)
            logger.info("💾 Расписания сохранены")
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения расписаний: {e}")
    
    def add_study_schedule(self, user_id: int, schedule_text: str) -> str:
        """Добавляет учебное расписание"""
        if user_id not in self.schedules:
            self.schedules[user_id] = {'study': [], 'work': []}
        
        schedule_item = {
            'id': len(self.schedules[user_id]['study']) + 1,
            'text': schedule_text,
            'added_at': datetime.now().isoformat(),
            'type': 'study'
        }
        
        self.schedules[user_id]['study'].append(schedule_item)
        self.save_schedules()
        
        return f"✅ Учебное расписание добавлено! ID: {schedule_item['id']}"
    
    def add_work_schedule(self, user_id: int, schedule_text: str) -> str:
        """Добавляет рабочее расписание"""
        if user_id not in self.schedules:
            self.schedules[user_id] = {'study': [], 'work': []}
        
        schedule_item = {
            'id': len(self.schedules[user_id]['work']) + 1,
            'text': schedule_text,
            'added_at': datetime.now().isoformat(),
            'type': 'work'
        }
        
        self.schedules[user_id]['work'].append(schedule_item)
        self.save_schedules()
        
        return f"✅ Рабочее расписание добавлено! ID: {schedule_item['id']}"
    
    def get_user_schedules(self, user_id: int) -> Dict:
        """Получает все расписания пользователя"""
        return self.schedules.get(user_id, {'study': [], 'work': []})
    
    def analyze_schedule(self, user_id: int) -> str:
        """Анализирует расписание и дает советы"""
        user_schedules = self.get_user_schedules(user_id)
        
        if not user_schedules['study'] and not user_schedules['work']:
            return "📝 У вас пока нет расписаний. Добавьте их для получения анализа!"
        
        analysis = "🔍 **Анализ вашего расписания:**\n\n"
        
        # Анализ учебного расписания
        if user_schedules['study']:
            study_count = len(user_schedules['study'])
            analysis += f"📚 **Учебное расписание:** {study_count} записей\n"
            
            # Простой анализ по ключевым словам
            study_text = " ".join([item['text'].lower() for item in user_schedules['study']])
            
            if 'математика' in study_text or 'матем' in study_text:
                analysis += "🧮 Математика - не забудьте калькулятор!\n"
            if 'физика' in study_text:
                analysis += "⚡ Физика - подготовьте формулы!\n"
            if 'химия' in study_text:
                analysis += "🧪 Химия - лабораторная работа?\n"
            if 'история' in study_text:
                analysis += "📚 История - повторите даты!\n"
            if 'английский' in study_text or 'англ' in study_text:
                analysis += "🇬🇧 Английский - готовьтесь к разговору!\n"
            
            analysis += "\n"
        
        # Анализ рабочего расписания
        if user_schedules['work']:
            work_count = len(user_schedules['work'])
            analysis += f"💼 **Рабочее расписание:** {work_count} записей\n"
            
            work_text = " ".join([item['text'].lower() for item in user_schedules['work']])
            
            if 'встреча' in work_text:
                analysis += "🤝 Встречи - подготовьте презентацию!\n"
            if 'дедлайн' in work_text or 'deadline' in work_text:
                analysis += "⏰ Дедлайны - не откладывайте на потом!\n"
            if 'звонок' in work_text:
                analysis += "📞 Звонки - проверьте связь!\n"
            
            analysis += "\n"
        
        # Общие советы
        total_items = len(user_schedules['study']) + len(user_schedules['work'])
        if total_items > 10:
            analysis += "⚠️ **Совет:** У вас много задач! Попробуйте приоритизировать.\n"
        elif total_items < 3:
            analysis += "💡 **Совет:** Добавьте больше деталей в расписание для лучшего планирования.\n"
        else:
            analysis += "✅ **Совет:** Хороший баланс задач! Держите темп.\n"
        
        return analysis

# Инициализация менеджера расписания
schedule_manager = ScheduleManager()

# Получение токена бота
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не найден в переменных окружения!")
    exit(1)

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Клавиатуры
def get_main_keyboard() -> InlineKeyboardMarkup:
    """Главная клавиатура"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📚 Добавить учебное", callback_data="add_study"),
        InlineKeyboardButton("💼 Добавить рабочее", callback_data="add_work")
    )
    keyboard.add(
        InlineKeyboardButton("📊 Мои расписания", callback_data="my_schedules"),
        InlineKeyboardButton("🔍 Анализ", callback_data="analyze")
    )
    keyboard.add(
        InlineKeyboardButton("🎤 Голосовое сообщение", callback_data="voice_input"),
        InlineKeyboardButton("❓ Помощь", callback_data="help")
    )
    return keyboard

def get_back_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой "Назад" """
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main"))
    return keyboard

# Обработчики команд
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    
    welcome_text = f"""
👋 Привет, {user_name}!

Я ваш персональный помощник по расписанию! 🗓️

Что я умею:
• 📚 Добавлять учебное расписание
• 💼 Добавлять рабочее расписание  
• 🎤 Принимать голосовые сообщения
• 🔍 Анализировать ваше расписание
• 💡 Давать полезные советы

Выберите действие:
"""
    
    await message.answer(welcome_text, reply_markup=get_main_keyboard())
    logger.info(f"🚀 Пользователь {user_id} запустил бота")

@dp.message_handler(commands=['help'])
async def cmd_help(message: types.Message):
    """Обработчик команды /help"""
    help_text = """
❓ **Как пользоваться ботом:**

1. **📚 Добавить учебное** - введите расписание пар, предметов, времени
2. **💼 Добавить рабочее** - введите рабочие задачи, встречи, дедлайны
3. **🎤 Голосовое** - отправьте голосовое сообщение с расписанием
4. **📊 Мои расписания** - просмотр всех ваших записей
5. **🔍 Анализ** - получайте умные советы по вашему расписанию

**Примеры:**
• "Понедельник 9:00 - Математика, аудитория 101"
• "Вторник 14:00 - Встреча с клиентом, подготовить отчет"
• "Среда - Дедлайн проекта, сдать до 18:00"

Бот запомнит все и поможет вам лучше планировать время! ⏰
"""
    
    await message.answer(help_text, reply_markup=get_back_keyboard())

@dp.message_handler(commands=['ping'])
async def cmd_ping(message: types.Message):
    """Обработчик команды /ping"""
    await message.answer("🏓 pong")
    logger.info(f"🏓 Пинг от пользователя {message.from_user.id}")

# Обработчики состояний
@dp.message_handler(state=ScheduleStates.waiting_for_study_schedule)
async def process_study_schedule(message: types.Message, state: FSMContext):
    """Обработчик учебного расписания"""
    user_id = message.from_user.id
    schedule_text = message.text
    
    result = schedule_manager.add_study_schedule(user_id, schedule_text)
    await message.answer(result, reply_markup=get_main_keyboard())
    
    await state.finish()
    logger.info(f"📚 Пользователь {user_id} добавил учебное расписание")

@dp.message_handler(state=ScheduleStates.waiting_for_work_schedule)
async def process_work_schedule(message: types.Message, state: FSMContext):
    """Обработчик рабочего расписания"""
    user_id = message.from_user.id
    schedule_text = message.text
    
    result = schedule_manager.add_work_schedule(user_id, schedule_text)
    await message.answer(result, reply_markup=get_main_keyboard())
    
    await state.finish()
    logger.info(f"💼 Пользователь {user_id} добавил рабочее расписание")

# Обработчик голосовых сообщений
@dp.message_handler(content_types=['voice'])
async def process_voice(message: types.Message):
    """Обработчик голосовых сообщений"""
    user_id = message.from_user.id
    
    # В реальном боте здесь была бы обработка голоса через speech-to-text
    # Пока просто предлагаем переписать текстом
    
    await message.answer(
        "🎤 Голосовое сообщение получено!\n\n"
        "К сожалению, пока не могу распознать голос. "
        "Пожалуйста, напишите расписание текстом или выберите тип:",
        reply_markup=get_main_keyboard()
    )
    
    logger.info(f"🎤 Пользователь {user_id} отправил голосовое сообщение")

# Обработчик callback-запросов
@dp.callback_query_handler(lambda c: True)
async def process_callback(callback_query: types.CallbackQuery, state: FSMContext):
    """Обработчик нажатий на кнопки"""
    user_id = callback_query.from_user.id
    data = callback_query.data
    
    await callback_query.answer()
    
    if data == "add_study":
        await callback_query.message.edit_text(
            "📚 **Добавление учебного расписания**\n\n"
            "Введите ваше учебное расписание:\n"
            "• День недели\n"
            "• Время\n"
            "• Предмет\n"
            "• Аудитория\n\n"
            "Пример: 'Понедельник 9:00 - Математика, аудитория 101'",
            reply_markup=get_back_keyboard()
        )
        await ScheduleStates.waiting_for_study_schedule.set()
        logger.info(f"📚 Пользователь {user_id} выбрал добавление учебного расписания")
    
    elif data == "add_work":
        await callback_query.message.edit_text(
            "💼 **Добавление рабочего расписания**\n\n"
            "Введите ваше рабочее расписание:\n"
            "• Задачи\n"
            "• Встречи\n"
            "• Дедлайны\n"
            "• Время\n\n"
            "Пример: 'Вторник 14:00 - Встреча с клиентом, подготовить отчет'",
            reply_markup=get_back_keyboard()
        )
        await ScheduleStates.waiting_for_work_schedule.set()
        logger.info(f"💼 Пользователь {user_id} выбрал добавление рабочего расписания")
    
    elif data == "my_schedules":
        user_schedules = schedule_manager.get_user_schedules(user_id)
        
        if not user_schedules['study'] and not user_schedules['work']:
            await callback_query.message.edit_text(
                "📝 **Ваши расписания**\n\n"
                "У вас пока нет добавленных расписаний.\n\n"
                "Добавьте первое расписание!",
                reply_markup=get_back_keyboard()
            )
        else:
            schedules_text = "📊 **Ваши расписания:**\n\n"
            
            if user_schedules['study']:
                schedules_text += "📚 **Учебное:**\n"
                for item in user_schedules['study']:
                    schedules_text += f"• ID {item['id']}: {item['text']}\n"
                schedules_text += "\n"
            
            if user_schedules['work']:
                schedules_text += "💼 **Рабочее:**\n"
                for item in user_schedules['work']:
                    schedules_text += f"• ID {item['id']}: {item['text']}\n"
            
            await callback_query.message.edit_text(
                schedules_text,
                reply_markup=get_back_keyboard()
            )
        
        logger.info(f"📊 Пользователь {user_id} просматривает свои расписания")
    
    elif data == "analyze":
        analysis = schedule_manager.analyze_schedule(user_id)
        await callback_query.message.edit_text(
            analysis,
            reply_markup=get_back_keyboard()
        )
        logger.info(f"🔍 Пользователь {user_id} запросил анализ расписания")
    
    elif data == "voice_input":
        await callback_query.message.edit_text(
            "🎤 **Голосовое сообщение**\n\n"
            "Отправьте голосовое сообщение с вашим расписанием.\n\n"
            "Пока что я не могу распознавать голос, но в будущем это будет доступно!",
            reply_markup=get_back_keyboard()
        )
        logger.info(f"🎤 Пользователь {user_id} выбрал голосовой ввод")
    
    elif data == "help":
        help_text = """
❓ **Как пользоваться ботом:**

1. **📚 Добавить учебное** - введите расписание пар, предметов, времени
2. **💼 Добавить рабочее** - введите рабочие задачи, встречи, дедлайны
3. **🎤 Голосовое** - отправьте голосовое сообщение с расписанием
4. **📊 Мои расписания** - просмотр всех ваших записей
5. **🔍 Анализ** - получайте умные советы по вашему расписанию

**Примеры:**
• "Понедельник 9:00 - Математика, аудитория 101"
• "Вторник 14:00 - Встреча с клиентом, подготовить отчет"
• "Среда - Дедлайн проекта, сдать до 18:00"

Бот запомнит все и поможет вам лучше планировать время! ⏰
"""
        await callback_query.message.edit_text(
            help_text,
            reply_markup=get_back_keyboard()
        )
    
    elif data == "back_to_main":
        await callback_query.message.edit_text(
            "🏠 **Главное меню**\n\n"
            "Выберите действие:",
            reply_markup=get_main_keyboard()
        )

# Обработчик ошибок
@dp.errors_handler()
async def errors_handler(update, exception):
    """Обработчик ошибок"""
    logger.error(f"❌ Ошибка: {exception}")
    try:
        raise exception
    except Exception as e:
        logger.error(f"❌ Необработанная ошибка: {e}")

async def main():
    """Главная функция"""
    logger.info("🚀 Запуск бота...")
    
    # Запускаем Flask в отдельном потоке для Render.com
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("🌐 Flask запущен в отдельном потоке")
    
    # Запускаем бота
    try:
        await dp.start_polling()
    except Exception as e:
        logger.error(f"❌ Ошибка запуска бота: {e}")
    finally:
        await bot.session.close()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
