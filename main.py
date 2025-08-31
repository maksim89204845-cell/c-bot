import os
import logging
from datetime import datetime, timedelta
import json
from typing import Dict, List, Optional
import threading
from flask import Flask, request, jsonify
import schedule
import time

# Импорты для telebot (pyTelegramBotAPI)
try:
    import telebot
    from telebot import TeleBot
    from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery
    logger.info(f"✅ pyTelegramBotAPI успешно импортирован")
except ImportError as e:
    logging.error(f"❌ Ошибка импорта pyTelegramBotAPI: {e}")
    logging.error("Установите: pip install pyTelegramBotAPI==4.14.0")
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

def send_daily_reminders():
    """Отправляет ежедневные напоминания всем пользователям"""
    try:
        # Получаем всех пользователей
        all_users = list(schedule_manager.schedules.keys())
        
        for user_id in all_users:
            try:
                today_schedule = schedule_manager.get_today_schedule(user_id)
                if "нет запланированных событий" not in today_schedule:
                    # Отправляем напоминание
                    bot.send_message(user_id, today_schedule)
                    logger.info(f"🌅 Отправлено ежедневное напоминание пользователю {user_id}")
                else:
                    logger.info(f"📅 Пользователь {user_id} не имеет событий на сегодня")
            except Exception as e:
                logger.error(f"❌ Ошибка отправки напоминания пользователю {user_id}: {e}")
        
        logger.info(f"✅ Ежедневные напоминания отправлены {len(all_users)} пользователям")
    except Exception as e:
        logger.error(f"❌ Ошибка в функции ежедневных напоминаний: {e}")

def run_scheduler():
    """Запускает планировщик задач"""
    # Ежедневное напоминание в 8:00
    schedule.every().day.at("08:00").do(send_daily_reminders)
    
    logger.info("⏰ Планировщик запущен: ежедневные напоминания в 8:00")
    
    while True:
        try:
            schedule.run_pending()
            time.sleep(60)  # Проверяем каждую минуту
        except Exception as e:
            logger.error(f"❌ Ошибка в планировщике: {e}")
            time.sleep(60)  # Продолжаем работу

# Состояния для бота
user_states = {}  # user_id -> state

class ScheduleManager:
    """Менеджер расписания пользователя по датам"""
    
    def __init__(self):
        self.schedules = {}  # user_id -> {date -> [events]}
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
    
    def parse_date(self, date_text: str) -> str:
        """Парсит дату из текста (например: '2 сентября' -> '2025-09-02')"""
        try:
            # Текущий год
            current_year = datetime.now().year
            
            # Словарь месяцев
            months = {
                'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4,
                'мая': 5, 'июня': 6, 'июля': 7, 'августа': 8,
                'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12
            }
            
            # Парсим текст
            parts = date_text.strip().split()
            if len(parts) >= 2:
                day = int(parts[0])
                month_name = parts[1].lower()
                
                if month_name in months:
                    month = months[month_name]
                    # Формируем дату в формате YYYY-MM-DD
                    date_obj = datetime(current_year, month, day)
                    return date_obj.strftime('%Y-%m-%d')
            
            # Если не удалось распарсить, возвращаем как есть
            return date_text
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга даты '{date_text}': {e}")
            return date_text
    
    def add_event(self, user_id: int, date_text: str, time_text: str, activity: str, event_type: str = "general") -> str:
        """Добавляет событие на конкретную дату"""
        if user_id not in self.schedules:
            self.schedules[user_id] = {}
        
        # Парсим дату
        date_key = self.parse_date(date_text)
        
        if date_key not in self.schedules[user_id]:
            self.schedules[user_id][date_key] = []
        
        # Генерируем уникальный ID
        import uuid
        event_id = str(uuid.uuid4())[:8]  # Короткий ID из 8 символов
        
        # Создаем событие
        event = {
            'id': event_id,
            'time': time_text.strip(),
            'activity': activity.strip(),
            'type': event_type,
            'added_at': datetime.now().isoformat()
        }
        
        # Добавляем событие и сортируем по времени
        self.schedules[user_id][date_key].append(event)
        self.schedules[user_id][date_key].sort(key=lambda x: x['time'])
        
        self.save_schedules()
        
        return f"✅ Событие добавлено на {date_text} в {time_text}: {activity}"
    
    def get_date_schedule(self, user_id: int, date_text: str) -> str:
        """Получает расписание на конкретную дату"""
        if user_id not in self.schedules:
            return "📝 У вас пока нет расписаний."
        
        date_key = self.parse_date(date_text)
        
        if date_key not in self.schedules[user_id] or not self.schedules[user_id][date_key]:
            return f"📅 На {date_text} у вас нет запланированных событий."
        
        events = self.schedules[user_id][date_key]
        
        result = f"📅 Расписание на {date_text}:\n\n"
        
        for i, event in enumerate(events, 1):
            emoji = "📚" if event['type'] == 'study' else "💼" if event['type'] == 'work' else "📝"
            result += f"{emoji} {event['time']} - {event['activity']}\n"
        
        return result
    
    def get_week_schedule(self, user_id: int) -> str:
        """Получает расписание на неделю"""
        if user_id not in self.schedules:
            return "📝 У вас пока нет расписаний."
        
        if not self.schedules[user_id]:
            return "📅 На этой неделе у вас нет запланированных событий."
        
        result = "📅 Расписание на неделю:\n\n"
        
        # Сортируем даты
        sorted_dates = sorted(self.schedules[user_id].keys())
        
        for date_key in sorted_dates:
            events = self.schedules[user_id][date_key]
            if events:
                # Преобразуем дату в читаемый формат
                try:
                    date_obj = datetime.strptime(date_key, '%Y-%m-%d')
                    date_display = date_obj.strftime('%d %B')
                except:
                    date_display = date_key
                
                result += f"📅 {date_display}:\n"
                
                for event in events:
                    emoji = "📚" if event['type'] == 'study' else "💼" if event['type'] == 'work' else "📝"
                    result += f"  {emoji} {event['time']} - {event['activity']}\n"
                
                result += "\n"
        
        return result
    
    def get_today_schedule(self, user_id: int) -> str:
        """Получает расписание на сегодня"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        if user_id not in self.schedules or today not in self.schedules[user_id]:
            return "📅 Сегодня у вас нет запланированных событий. Отличный день для отдыха! 😊"
        
        events = self.schedules[user_id][today]
        if not events:
            return "📅 Сегодня у вас нет запланированных событий. Отличный день для отдыха! 😊"
        
        result = "🌅 Доброе утро! Вот что у вас сегодня:\n\n"
        
        for i, event in enumerate(events, 1):
            emoji = "📚" if event['type'] == 'study' else "💼" if event['type'] == 'work' else "📝"
            result += f"{i}. {emoji} {event['time']} - {event['activity']}\n"
        
        result += "\n💡 Совет: Планируйте время с запасом между событиями!"
        return result
    
    def get_user_schedules(self, user_id: int) -> Dict:
        """Получает все расписания пользователя"""
        return self.schedules.get(user_id, {})
    
    def analyze_schedule(self, user_id: int) -> str:
        """Анализирует расписание и дает советы"""
        user_schedules = self.get_user_schedules(user_id)
        
        if not user_schedules['study'] and not user_schedules['work']:
            return "📝 У вас пока нет расписаний. Добавьте их для получения анализа!"
        
        analysis = "🔍 Анализ вашего расписания:\n\n"
        
        # Анализ по типам событий
        study_count = 0
        work_count = 0
        total_events = 0
        
        for date_key, events in self.schedules[user_id].items():
            for event in events:
                total_events += 1
                if event.get('type') == 'study':
                    study_count += 1
                elif event.get('type') == 'work':
                    work_count += 1
        
        analysis += f"📊 Общая статистика:\n"
        analysis += f"• Всего событий: {total_events}\n"
        analysis += f"• Учебных: {study_count}\n"
        analysis += f"• Рабочих: {work_count}\n\n"
        
        # Анализ по дням недели
        weekday_stats = {}
        for date_key, events in self.schedules[user_id].items():
            try:
                date_obj = datetime.strptime(date_key, '%Y-%m-%d')
                weekday = date_obj.strftime('%A')  # Monday, Tuesday, etc.
                if weekday not in weekday_stats:
                    weekday_stats[weekday] = 0
                weekday_stats[weekday] += len(events)
            except:
                pass
        
        # Самый загруженный день
        if weekday_stats:
            busiest_day = max(weekday_stats.items(), key=lambda x: x[1])
            analysis += f"📅 Самый загруженный день: {busiest_day[0]} ({busiest_day[1]} событий)\n\n"
        
        # Советы
        analysis += "💡 Советы:\n"
        if total_events > 15:
            analysis += "• У вас очень насыщенное расписание! Рассмотрите делегирование.\n"
        elif total_events > 10:
            analysis += "• Хорошая загруженность! Не забудьте про отдых.\n"
        elif total_events > 5:
            analysis += "• Умеренная загруженность. Можно добавить больше активности.\n"
        else:
            analysis += "• Легкая загруженность. Отличное время для новых проектов!\n"
        
        if study_count > work_count * 2:
            analysis += "• Большой акцент на учебе - отличная инвестиция в будущее!\n"
        elif work_count > study_count * 2:
            analysis += "• Много рабочих событий - не забывайте про развитие!\n"
        
        return analysis

    def get_smart_recommendations(self, user_id: int) -> str:
        """Генерирует краткие рекомендации по расписанию"""
        if user_id not in self.schedules:
            return "📊 Рекомендации\n\nДобавьте события для получения советов!"
        
        result = "🤖 Рекомендации ИИ:\n\n"
        
        # Считаем события
        total_events = sum(len(events) for events in self.schedules[user_id].values())
        study_count = sum(1 for events in self.schedules[user_id].values() 
                         for event in events if event.get('type') == 'study')
        work_count = sum(1 for events in self.schedules[user_id].values() 
                        for event in events if event.get('type') == 'work')
        
        # Краткая статистика
        result += f"📊 Статистика: {total_events} событий\n"
        result += f"📚 Учеба: {study_count} | 💼 Работа: {work_count}\n\n"
        
        # Основные рекомендации
        if total_events == 0:
            result += "💡 Добавьте события в расписание\n"
        elif total_events < 5:
            result += "💡 Добавьте больше событий\n"
        elif total_events > 15:
            result += "⚠️ Слишком много событий - добавьте отдых\n"
        else:
            result += "✅ Хорошее количество событий\n"
        
        # Баланс
        if study_count > work_count * 2:
            result += "📚 Много учебы - добавьте работу\n"
        elif work_count > study_count * 2:
            result += "💼 Много работы - добавьте учебу\n"
        else:
            result += "⚖️ Хороший баланс учеба/работа\n"
        
        result += "\n🎯 Используйте ИИ-планировщик для оптимизации!"
        
        return result

# Инициализация менеджера расписания
schedule_manager = ScheduleManager()

# Получение токена бота
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не найден в переменных окружения!")
    exit(1)

# Клавиатуры
def get_main_keyboard() -> InlineKeyboardMarkup:
    """Главная клавиатура"""
    keyboard = [
        [
            InlineKeyboardButton("📚 Добавить учебное", callback_data="add_study"),
            InlineKeyboardButton("💼 Добавить рабочее", callback_data="add_work")
        ],
        [
            InlineKeyboardButton("📊 Мои расписания", callback_data="my_schedules"),
            InlineKeyboardButton("🔍 Анализ", callback_data="analyze")
        ],
        [
            InlineKeyboardButton("🎤 Голосовое сообщение", callback_data="voice_input"),
            InlineKeyboardButton("❓ Помощь", callback_data="help")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_back_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой "Назад" """
    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")]]
    return InlineKeyboardMarkup(keyboard)

# Обработчики команд
def cmd_start(update, context):
    """Обработчик команды /start"""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    
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
    
    update.message.reply_text(welcome_text, reply_markup=get_main_keyboard())
    logger.info(f"🚀 Пользователь {user_id} запустил бота")

def cmd_help(update, context):
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
    
    update.message.reply_text(help_text, reply_markup=get_back_keyboard())

def cmd_ping(update, context):
    """Обработчик команды /ping"""
    update.message.reply_text("🏓 pong")
    logger.info(f"🏓 Пинг от пользователя {update.effective_user.id}")

# Обработчики состояний
def add_study_start(update, context):
    """Начало добавления учебного расписания"""
    update.callback_query.answer()
    update.callback_query.edit_message_text(
        "📚 **Добавление учебного расписания**\n\n"
        "Введите ваше учебное расписание:\n"
        "• День недели\n"
        "• Время\n"
        "• Предмет\n"
        "• Аудитория\n\n"
        "Пример: 'Понедельник 9:00 - Математика, аудитория 101'",
        reply_markup=get_back_keyboard()
    )
    return WAITING_FOR_STUDY_SCHEDULE

def add_work_start(update, context):
    """Начало добавления рабочего расписания"""
    update.callback_query.answer()
    update.callback_query.edit_message_text(
        "💼 **Добавление рабочего расписания**\n\n"
        "Введите ваше рабочее расписание:\n"
        "• Задачи\n"
        "• Встречи\n"
        "• Дедлайны\n"
        "• Время\n\n"
        "Пример: 'Вторник 14:00 - Встреча с клиентом, подготовить отчет'",
        reply_markup=get_back_keyboard()
    )
    return WAITING_FOR_WORK_SCHEDULE

def process_study_schedule(update, context):
    """Обработчик учебного расписания"""
    user_id = update.effective_user.id
    schedule_text = update.message.text
    
    result = schedule_manager.add_study_schedule(user_id, schedule_text)
    update.message.reply_text(result, reply_markup=get_main_keyboard())
    
    logger.info(f"📚 Пользователь {user_id} добавил учебное расписание")
    return ConversationHandler.END

def process_work_schedule(update, context):
    """Обработчик рабочего расписания"""
    user_id = update.effective_user.id
    schedule_text = update.message.text
    
    result = schedule_manager.add_work_schedule(user_id, schedule_text)
    update.message.reply_text(result, reply_markup=get_main_keyboard())
    
    logger.info(f"💼 Пользователь {user_id} добавил рабочее расписание")
    return ConversationHandler.END

def cancel(update, context):
    """Отмена операции"""
    update.callback_query.answer()
    update.callback_query.edit_message_text(
        "🏠 **Главное меню**\n\n"
        "Выберите действие:",
        reply_markup=get_main_keyboard()
    )
    return ConversationHandler.END

# Обработчик голосовых сообщений
async def process_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик голосовых сообщений"""
    user_id = update.effective_user.id
    
    # В реальном боте здесь была бы обработка голоса через speech-to-text
    # Пока просто предлагаем переписать текстом
    
    await update.message.reply_text(
        "🎤 Голосовое сообщение получено!\n\n"
        "К сожалению, пока не могу распознать голос. "
        "Пожалуйста, напишите расписание текстом или выберите тип:",
        reply_markup=get_main_keyboard()
    )
    
    logger.info(f"🎤 Пользователь {user_id} отправил голосовое сообщение")

# Обработчик callback-запросов
async def process_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    user_id = update.effective_user.id
    data = update.callback_query.data
    
    await update.callback_query.answer()
    
    if data == "my_schedules":
        user_schedules = schedule_manager.get_user_schedules(user_id)
        
        if not user_schedules['study'] and not user_schedules['work']:
            await update.callback_query.edit_message_text(
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
            
            await update.callback_query.edit_message_text(
                schedules_text,
                reply_markup=get_back_keyboard()
            )
        
        logger.info(f"📊 Пользователь {user_id} просматривает свои расписания")
    
    elif data == "analyze":
        analysis = schedule_manager.analyze_schedule(user_id)
        await update.callback_query.edit_message_text(
            analysis,
            reply_markup=get_back_keyboard()
        )
        logger.info(f"🔍 Пользователь {user_id} запросил анализ расписания")
    
    elif data == "voice_input":
        await update.callback_query.edit_message_text(
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
        await update.callback_query.edit_message_text(
            help_text,
            reply_markup=get_back_keyboard()
        )
    
    elif data == "back_to_main":
        await update.callback_query.edit_message_text(
            "🏠 **Главное меню**\n\n"
            "Выберите действие:",
            reply_markup=get_main_keyboard()
        )

async def main():
    """Главная функция"""
    logger.info("🚀 Запуск бота...")
    
    # Запускаем Flask в отдельном потоке для Render.com
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("🌐 Flask запущен в отдельном потоке")
    
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Добавляем обработчики команд
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("ping", cmd_ping))
    
    # Добавляем обработчик голосовых сообщений
    application.add_handler(MessageHandler(filters.VOICE, process_voice))
    
    # Добавляем ConversationHandler для добавления расписания
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(add_study_start, pattern="^add_study$"),
            CallbackQueryHandler(add_work_start, pattern="^add_work$")
        ],
        states={
            WAITING_FOR_STUDY_SCHEDULE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_study_schedule)],
            WAITING_FOR_WORK_SCHEDULE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_work_schedule)]
        },
        fallbacks=[CallbackQueryHandler(cancel, pattern="^back_to_main$")]
    )
    
    application.add_handler(conv_handler)
    
    # Добавляем обработчик callback-запросов
    application.add_handler(CallbackQueryHandler(process_callback))
    
    # Запускаем бота
    try:
        logger.info("🤖 Бот запущен и готов к работе!")
        await application.initialize()
        await application.start()
        await application.run_polling()
    except Exception as e:
        logger.error(f"❌ Ошибка запуска бота: {e}")
    finally:
        await application.stop()
        await application.shutdown()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
