import os
import logging
from datetime import datetime, timedelta
import json
from typing import Dict, List, Optional
import threading
from flask import Flask, request, jsonify
import schedule
import time

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
        schedule.run_pending()
        time.sleep(60)  # Проверяем каждую минуту

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
        
        return f"✅ Событие добавлено на {date_text} в {time_text}: {activity}\n🆔 ID: {event_id}"
    
    def get_date_schedule(self, user_id: int, date_text: str) -> str:
        """Получает расписание на конкретную дату"""
        if user_id not in self.schedules:
            return "📝 У вас пока нет расписаний."
        
        date_key = self.parse_date(date_text)
        
        if date_key not in self.schedules[user_id] or not self.schedules[user_id][date_key]:
            return f"📅 На {date_text} у вас нет запланированных событий."
        
        events = self.schedules[user_id][date_key]
        
        result = f"📅 **Расписание на {date_text}:**\n\n"
        
        for i, event in enumerate(events, 1):
            emoji = "📚" if event['type'] == 'study' else "💼" if event['type'] == 'work' else "📝"
            result += f"{emoji} **{event['time']}** - {event['activity']} [ID: {event['id']}]\n"
        
        return result
    
    def get_week_schedule(self, user_id: int) -> str:
        """Получает расписание на неделю"""
        if user_id not in self.schedules:
            return "📝 У вас пока нет расписаний."
        
        if not self.schedules[user_id]:
            return "📅 На этой неделе у вас нет запланированных событий."
        
        result = "📅 **Расписание на неделю:**\n\n"
        
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
                
                result += f"📅 **{date_display}:**\n"
                
                for event in events:
                    emoji = "📚" if event['type'] == 'study' else "💼" if event['type'] == 'work' else "📝"
                    result += f"  {emoji} **{event['time']}** - {event['activity']} [ID: {event['id']}]\n"
                
                result += "\n"
        
        return result
    
    def clear_date(self, user_id: int, date_text: str) -> str:
        """Очищает расписание на конкретную дату"""
        if user_id not in self.schedules:
            return "📝 У вас пока нет расписаний."
        
        date_key = self.parse_date(date_text)
        
        if date_key not in self.schedules[user_id]:
            return f"📅 На {date_text} у вас нет запланированных событий."
        
        events_count = len(self.schedules[user_id][date_key])
        del self.schedules[user_id][date_key]
        self.save_schedules()
        
        return f"🗑️ Очищено {events_count} событий на {date_text}"
    
    def get_user_schedules(self, user_id: int) -> Dict:
        """Получает все расписания пользователя"""
        return self.schedules.get(user_id, {})
    
    def analyze_schedule(self, user_id: int) -> str:
        """Анализирует расписание и дает советы"""
        user_schedules = self.get_user_schedules(user_id)
        
        if not user_schedules:
            return "📝 У вас пока нет расписаний. Добавьте их для получения анализа!"
        
        analysis = "🔍 **Анализ вашего расписания:**\n\n"
        
        total_events = sum(len(events) for events in user_schedules.values())
        total_days = len(user_schedules)
        
        analysis += f"📊 **Общая статистика:**\n"
        analysis += f"• Всего событий: {total_events}\n"
        analysis += f"• Дней с расписанием: {total_days}\n"
        analysis += f"• Среднее событий в день: {total_events/total_days:.1f}\n\n"
        
        # Анализ по типам событий
        study_count = sum(1 for events in user_schedules.values() 
                         for event in events if event.get('type') == 'study')
        work_count = sum(1 for events in user_schedules.values() 
                        for event in events if event.get('type') == 'work')
        
        if study_count > 0:
            analysis += f"📚 **Учебные события:** {study_count}\n"
        if work_count > 0:
            analysis += f"💼 **Рабочие события:** {work_count}\n"
        
        # Советы
        analysis += "\n💡 **Советы:**\n"
        if total_events > 10:
            analysis += "• У вас насыщенное расписание! Не забудьте про отдых.\n"
        if study_count > work_count:
            analysis += "• Больше учебных событий - отличная учеба!\n"
        if work_count > study_count:
            analysis += "• Больше рабочих событий - продуктивная работа!\n"
        
        return analysis
    
    def get_event_by_id(self, user_id: int, event_id: str) -> Optional[Dict]:
        """Получает событие по ID"""
        if user_id not in self.schedules:
            return None
        
        for date_key, events in self.schedules[user_id].items():
            for event in events:
                if event.get('id') == event_id:
                    return {'event': event, 'date_key': date_key}
        return None
    
    def edit_event(self, user_id: int, event_id: str, field: str, new_value: str) -> str:
        """Редактирует событие"""
        event_info = self.get_event_by_id(user_id, event_id)
        if not event_info:
            return "❌ Событие не найдено!"
        
        event = event_info['event']
        date_key = event_info['date_key']
        
        if field == 'time':
            event['time'] = new_value
            # Пересортируем события по времени
            self.schedules[user_id][date_key].sort(key=lambda x: x['time'])
            message = f"✅ Время события изменено на: {new_value}"
        elif field == 'description':
            event['activity'] = new_value
            message = f"✅ Описание события изменено на: {new_value}"
        elif field == 'date':
            # Перемещаем событие на новую дату
            new_date_key = self.parse_date(new_value)
            if new_date_key != date_key:
                # Удаляем с старой даты
                self.schedules[user_id][date_key].remove(event)
                # Добавляем на новую дату
                if new_date_key not in self.schedules[user_id]:
                    self.schedules[user_id][new_date_key] = []
                self.schedules[user_id][new_date_key].append(event)
                # Сортируем по времени
                self.schedules[user_id][new_date_key].sort(key=lambda x: x['time'])
                message = f"✅ Событие перемещено на: {new_value}"
            else:
                message = "ℹ️ Дата не изменилась"
        else:
            return "❌ Неизвестное поле для редактирования!"
        
        self.save_schedules()
        return message
    
    def get_today_schedule(self, user_id: int) -> str:
        """Получает расписание на сегодня"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        if user_id not in self.schedules or today not in self.schedules[user_id]:
            return "📅 Сегодня у вас нет запланированных событий. Отличный день для отдыха! 😊"
        
        events = self.schedules[user_id][today]
        if not events:
            return "📅 Сегодня у вас нет запланированных событий. Отличный день для отдыха! 😊"
        
        result = "🌅 **Доброе утро! Вот что у вас сегодня:**\n\n"
        
        for i, event in enumerate(events, 1):
            emoji = "📚" if event['type'] == 'study' else "💼" if event['type'] == 'work' else "📝"
            result += f"{i}. {emoji} **{event['time']}** - {event['activity']}\n"
        
        result += "\n💡 **Совет:** Планируйте время с запасом между событиями!"
        return result
    
    def get_statistics(self, user_id: int) -> str:
        """Получает подробную статистику"""
        user_schedules = self.get_user_schedules(user_id)
        
        if not user_schedules:
            return "📝 У вас пока нет расписаний для анализа."
        
        total_events = sum(len(events) for events in user_schedules.values())
        total_days = len(user_schedules)
        
        # Статистика по типам
        study_count = sum(1 for events in user_schedules.values() 
                         for event in events if event.get('type') == 'study')
        work_count = sum(1 for events in user_schedules.values() 
                        for event in events if event.get('type') == 'work')
        general_count = total_events - study_count - work_count
        
        # Статистика по дням недели
        weekday_stats = {}
        for date_key, events in user_schedules.items():
            try:
                date_obj = datetime.strptime(date_key, '%Y-%m-%d')
                weekday = date_obj.strftime('%A')  # Monday, Tuesday, etc.
                if weekday not in weekday_stats:
                    weekday_stats[weekday] = 0
                weekday_stats[weekday] += len(events)
            except:
                pass
        
        # Самый загруженный день
        busiest_day = max(weekday_stats.items(), key=lambda x: x[1]) if weekday_stats else None
        
        result = "📊 **Подробная статистика вашего расписания:**\n\n"
        
        result += f"📈 **Общие показатели:**\n"
        result += f"• Всего событий: {total_events}\n"
        result += f"• Дней с расписанием: {total_days}\n"
        result += f"• Среднее событий в день: {total_events/total_days:.1f}\n\n"
        
        result += f"🏷️ **По типам событий:**\n"
        result += f"• 📚 Учебные: {study_count} ({study_count/total_events*100:.1f}%)\n"
        result += f"• 💼 Рабочие: {work_count} ({work_count/total_events*100:.1f}%)\n"
        result += f"• 📝 Общие: {general_count} ({general_count/total_events*100:.1f}%)\n\n"
        
        if busiest_day:
            result += f"📅 **Самый загруженный день:** {busiest_day[0]} ({busiest_day[1]} событий)\n\n"
        
        result += f"💡 **Рекомендации:**\n"
        if total_events > 15:
            result += "• У вас очень насыщенное расписание! Рассмотрите делегирование.\n"
        elif total_events > 10:
            result += "• Хорошая загруженность! Не забудьте про отдых.\n"
        elif total_events > 5:
            result += "• Умеренная загруженность. Можно добавить больше активности.\n"
        else:
            result += "• Легкая загруженность. Отличное время для новых проектов!\n"
        
        if study_count > work_count * 2:
            result += "• Большой акцент на учебе - отличная инвестиция в будущее!\n"
        elif work_count > study_count * 2:
            result += "• Много рабочих событий - не забывайте про развитие!\n"
        
        return result

# Инициализация менеджера расписания
schedule_manager = ScheduleManager()

# Получение токена бота
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не найден в переменных окружения!")
    exit(1)

# Инициализация бота
bot = TeleBot(BOT_TOKEN)

# Клавиатуры
def get_main_keyboard() -> InlineKeyboardMarkup:
    """Главная клавиатура"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("➕ Добавить событие", callback_data="add_event"),
        InlineKeyboardButton("📅 Расписание на дату", callback_data="show_date")
    )
    keyboard.add(
        InlineKeyboardButton("📊 Расписание на неделю", callback_data="show_week"),
        InlineKeyboardButton("🔍 Анализ", callback_data="analyze")
    )
    keyboard.add(
        InlineKeyboardButton("✏️ Редактировать", callback_data="edit_event"),
        InlineKeyboardButton("📈 Статистика", callback_data="statistics")
    )
    keyboard.add(
        InlineKeyboardButton("🗑️ Очистить дату", callback_data="clear_date"),
        InlineKeyboardButton("❓ Помощь", callback_data="help")
    )
    return keyboard

def get_back_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой "Назад" """
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main"))
    return keyboard

# Обработчики команд
@bot.message_handler(commands=['start'])
def cmd_start(message: Message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    
    welcome_text = f"""
👋 Привет, {user_name}!

Я ваш персональный помощник по расписанию! 🗓️

Что я умею:
• ➕ Добавлять события на конкретные даты
• 📅 Показывать расписание на дату/неделю
• 🔍 Анализировать ваше расписание
• 💡 Давать полезные советы
• 🗑️ Очищать расписание по датам

Пример добавления:
"2 сентября 13:55-15:50 Реабилитация и абилитация"

Выберите действие:
"""
    
    bot.reply_to(message, welcome_text, reply_markup=get_main_keyboard())
    logger.info(f"🚀 Пользователь {user_id} запустил бота")

@bot.message_handler(commands=['help'])
def cmd_help(message: Message):
    """Обработчик команды /help"""
    help_text = """
❓ **Как пользоваться ботом:**

1. **➕ Добавить событие** - добавьте событие на конкретную дату
2. **📅 Расписание на дату** - посмотрите что запланировано на определенную дату
3. **📊 Расписание на неделю** - обзор всех событий на неделю
4. **🔍 Анализ** - получайте умные советы по вашему расписанию
5. **✏️ Редактировать** - измените время, описание или дату события
6. **📈 Статистика** - подробная аналитика вашего расписания
7. **🗑️ Очистить дату** - удалите все события на конкретную дату

**Команды:**
• `/add` - быстрое добавление события
• `/show` - показать расписание на неделю
• `/today` - что у вас сегодня
• `/help` - эта справка

**Формат добавления события:**
Дата Время Описание

**Примеры:**
• "2 сентября 13:55-15:50 Реабилитация и абилитация"
• "3 сентября 09:00-10:30 Математика, аудитория 101"
• "4 сентября 16:30-17:00 Работа в Т-Мобайл"

**Редактирование:**
• "время 14:00-15:30" - изменить время
• "описание Новая встреча" - изменить описание
• "дата 5 сентября" - переместить на другую дату

**Формат даты:**
• "2 сентября" (автоматически определится как 2025-09-02)
• "15 октября"
• "3 ноября"

Бот автоматически определит тип события (учебное/рабочее) и отсортирует по времени! ⏰
"""
    
    bot.reply_to(message, help_text, reply_markup=get_back_keyboard())

@bot.message_handler(commands=['ping'])
def cmd_ping(message: Message):
    """Обработчик команды /ping"""
    bot.reply_to(message, "🏓 pong")
    logger.info(f"🏓 Пинг от пользователя {message.from_user.id}")

@bot.message_handler(commands=['add'])
def cmd_add(message: Message):
    """Обработчик команды /add - быстрое добавление события"""
    user_id = message.from_user.id
    user_states[user_id] = 'waiting_for_event'
    
    bot.reply_to(
        message,
        "➕ **Быстрое добавление события**\n\n"
        "Введите событие в формате:\n"
        "Дата Время Описание\n\n"
        "Примеры:\n"
        "• 2 сентября 13:55-15:50 Реабилитация и абилитация\n"
        "• 3 сентября 09:00-10:30 Математика, аудитория 101\n"
        "• 4 сентября 16:30-17:00 Работа в Т-Мобайл",
        reply_markup=get_back_keyboard()
    )
    logger.info(f"➕ Пользователь {user_id} использовал команду /add")

@bot.message_handler(commands=['show'])
def cmd_show(message: Message):
    """Обработчик команды /show - показать расписание на неделю"""
    user_id = message.from_user.id
    result = schedule_manager.get_week_schedule(user_id)
    
    bot.reply_to(message, result, reply_markup=get_main_keyboard())
    logger.info(f"📊 Пользователь {user_id} использовал команду /show")

@bot.message_handler(commands=['today'])
def cmd_today(message: Message):
    """Обработчик команды /today - показать расписание на сегодня"""
    user_id = message.from_user.id
    result = schedule_manager.get_today_schedule(user_id)
    
    bot.reply_to(message, result, reply_markup=get_main_keyboard())
    logger.info(f"📅 Пользователь {user_id} использовал команду /today")

# Обработчик голосовых сообщений
@bot.message_handler(content_types=['voice'])
def process_voice(message: Message):
    """Обработчик голосовых сообщений"""
    user_id = message.from_user.id
    
    bot.reply_to(
        message,
        "🎤 Голосовое сообщение получено!\n\n"
        "К сожалению, пока не могу распознать голос. "
        "Пожалуйста, напишите событие текстом в формате:\n"
        "Дата Время Описание\n\n"
        "Пример: '2 сентября 13:55-15:50 Реабилитация и абилитация'",
        reply_markup=get_main_keyboard()
    )
    
    logger.info(f"🎤 Пользователь {user_id} отправил голосовое сообщение")

# Обработчик текстовых сообщений для добавления расписания
@bot.message_handler(func=lambda message: True)
def handle_text(message: Message):
    """Обработчик текстовых сообщений"""
    user_id = message.from_user.id
    
    if user_id in user_states:
        state = user_states[user_id]
        
        if state == 'waiting_for_event':
            # Парсим сообщение в формате: "2 сентября 13:55-15:50 Реабилитация и абилитация"
            try:
                parts = message.text.strip().split()
                if len(parts) >= 4:
                    # Первые 2 части - дата (например: "2 сентября")
                    date_part = f"{parts[0]} {parts[1]}"
                    # 3-я часть - время (например: "13:55-15:50")
                    time_part = parts[2]
                    # Остальное - описание активности
                    activity_part = " ".join(parts[3:])
                    
                    # Определяем тип события
                    event_type = "general"
                    if any(word in activity_part.lower() for word in ['математика', 'физика', 'химия', 'история', 'английский', 'реабилитация', 'абилитация']):
                        event_type = "study"
                    elif any(word in activity_part.lower() for word in ['работа', 'встреча', 'звонок', 'дедлайн', 'deadline']):
                        event_type = "work"
                    
                    result = schedule_manager.add_event(user_id, date_part, time_part, activity_part, event_type)
                    bot.reply_to(message, result, reply_markup=get_main_keyboard())
                    logger.info(f"✅ Пользователь {user_id} добавил событие: {date_part} {time_part} {activity_part}")
                else:
                    bot.reply_to(message, 
                        "❌ Неверный формат! Используйте:\n"
                        "Дата Время Описание\n\n"
                        "Пример: '2 сентября 13:55-15:50 Реабилитация и абилитация'",
                        reply_markup=get_main_keyboard())
                    logger.warning(f"❌ Пользователь {user_id} ввел неверный формат: {message.text}")
                    return
            except Exception as e:
                bot.reply_to(message, 
                    "❌ Ошибка при добавлении события. Проверьте формат:\n"
                    "Дата Время Описание\n\n"
                    "Пример: '2 сентября 13:55-15:50 Реабилитация и абилитация'",
                    reply_markup=get_main_keyboard())
                logger.error(f"❌ Ошибка при добавлении события пользователем {user_id}: {e}")
                return
            finally:
                del user_states[user_id]
            
        elif state == 'waiting_for_date':
            result = schedule_manager.get_date_schedule(user_id, message.text)
            bot.reply_to(message, result, reply_markup=get_main_keyboard())
            del user_states[user_id]
            logger.info(f"📅 Пользователь {user_id} запросил расписание на {message.text}")
            
        elif state == 'waiting_for_clear_date':
            result = schedule_manager.clear_date(user_id, message.text)
            bot.reply_to(message, result, reply_markup=get_main_keyboard())
            del user_states[user_id]
            logger.info(f"🗑️ Пользователь {user_id} очистил расписание на {message.text}")
            
        elif state == 'waiting_for_event_id':
            # Показываем событие и предлагаем что редактировать
            event_info = schedule_manager.get_event_by_id(user_id, message.text)
            if event_info:
                event = event_info['event']
                user_states[user_id] = f'editing_{message.text}'
                
                bot.reply_to(
                    message,
                    f"✏️ **Редактирование события:**\n\n"
                    f"📅 **{event['time']}** - {event['activity']}\n"
                    f"🏷️ Тип: {event['type']}\n\n"
                    f"Что хотите изменить?\n"
                    f"• Введите 'время НОВОЕ_ВРЕМЯ' (например: время 14:00-15:30)\n"
                    f"• Введите 'описание НОВОЕ_ОПИСАНИЕ' (например: описание Новая встреча)\n"
                    f"• Введите 'дата НОВАЯ_ДАТА' (например: дата 5 сентября)",
                    reply_markup=get_back_keyboard()
                )
                logger.info(f"✏️ Пользователь {user_id} выбрал событие для редактирования: {message.text}")
            else:
                bot.reply_to(
                    message,
                    "❌ Событие с таким ID не найдено!\n\n"
                    "Проверьте ID в расписании или используйте команду /show",
                    reply_markup=get_main_keyboard()
                )
                del user_states[user_id]
                logger.warning(f"❌ Пользователь {user_id} ввел неверный ID: {message.text}")
            
        elif state.startswith('editing_'):
            # Обработка редактирования конкретного поля
            event_id = state.split('_')[1]
            parts = message.text.strip().split(' ', 1)
            
            if len(parts) >= 2:
                field = parts[0].lower()
                new_value = parts[1]
                
                if field in ['время', 'описание', 'дата']:
                    # Преобразуем русские названия полей в английские
                    field_map = {'время': 'time', 'описание': 'description', 'дата': 'date'}
                    result = schedule_manager.edit_event(user_id, event_id, field_map[field], new_value)
                    bot.reply_to(message, result, reply_markup=get_main_keyboard())
                    logger.info(f"✏️ Пользователь {user_id} отредактировал {field} события {event_id}")
                else:
                    bot.reply_to(
                        message,
                        "❌ Неверный формат! Используйте:\n"
                        "• время НОВОЕ_ВРЕМЯ\n"
                        "• описание НОВОЕ_ОПИСАНИЕ\n"
                        "• дата НОВАЯ_ДАТА",
                        reply_markup=get_main_keyboard()
                    )
            else:
                bot.reply_to(
                    message,
                    "❌ Неверный формат! Используйте:\n"
                    "• время НОВОЕ_ВРЕМЯ\n"
                    "• описание НОВОЕ_ОПИСАНИЕ\n"
                    "• дата НОВАЯ_ДАТА",
                    reply_markup=get_main_keyboard()
                )
            
            del user_states[user_id]
            
        else:
            del user_states[user_id]
            bot.reply_to(message, "❌ Неизвестное состояние. Попробуйте снова.", reply_markup=get_main_keyboard())

# Обработчик callback-запросов
@bot.callback_query_handler(func=lambda call: True)
def process_callback(call: CallbackQuery):
    """Обработчик нажатий на кнопки"""
    user_id = call.from_user.id
    data = call.data
    
    bot.answer_callback_query(call.id)
    
    if data == "add_event":
        user_states[user_id] = 'waiting_for_event'
        bot.edit_message_text(
            "➕ **Добавление события**\n\n"
            "Введите событие в формате:\n"
            "Дата Время Описание\n\n"
            "Примеры:\n"
            "• 2 сентября 13:55-15:50 Реабилитация и абилитация\n"
            "• 3 сентября 09:00-10:30 Математика, аудитория 101\n"
            "• 4 сентября 16:30-17:00 Работа в Т-Мобайл\n\n"
            "Бот автоматически определит тип события (учебное/рабочее)",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_back_keyboard()
        )
        logger.info(f"➕ Пользователь {user_id} выбрал добавление события")
    
    elif data == "show_date":
        user_states[user_id] = 'waiting_for_date'
        bot.edit_message_text(
            "📅 **Показать расписание на дату**\n\n"
            "Введите дату в формате:\n"
            "• 2 сентября\n"
            "• 15 октября\n"
            "• 3 ноября\n\n"
            "Или просто число месяца",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_back_keyboard()
        )
        logger.info(f"📅 Пользователь {user_id} выбрал просмотр расписания на дату")
    
    elif data == "show_week":
        result = schedule_manager.get_week_schedule(user_id)
        bot.edit_message_text(
            result,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_back_keyboard()
        )
        logger.info(f"📊 Пользователь {user_id} запросил расписание на неделю")
    
    elif data == "clear_date":
        user_states[user_id] = 'waiting_for_clear_date'
        bot.edit_message_text(
            "🗑️ **Очистить расписание на дату**\n\n"
            "Введите дату, которую хотите очистить:\n"
            "• 2 сентября\n"
            "• 15 октября\n"
            "• 3 ноября\n\n"
            "⚠️ Внимание: все события на эту дату будут удалены!",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_back_keyboard()
        )
        logger.info(f"🗑️ Пользователь {user_id} выбрал очистку расписания на дату")
    
    elif data == "edit_event":
        user_states[user_id] = 'waiting_for_event_id'
        bot.edit_message_text(
            "✏️ **Редактирование события**\n\n"
            "Введите ID события, которое хотите отредактировать:\n"
            "ID можно найти в расписании (например: a1b2c3d4)\n\n"
            "Или используйте команду /show для просмотра расписания",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_back_keyboard()
        )
        logger.info(f"✏️ Пользователь {user_id} выбрал редактирование события")
    
    elif data == "statistics":
        result = schedule_manager.get_statistics(user_id)
        bot.edit_message_text(
            result,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_back_keyboard()
        )
        logger.info(f"📈 Пользователь {user_id} запросил статистику")
    
    elif data == "analyze":
        analysis = schedule_manager.analyze_schedule(user_id)
        bot.edit_message_text(
            analysis,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_back_keyboard()
        )
        logger.info(f"🔍 Пользователь {user_id} запросил анализ расписания")
    
    elif data == "help":
        help_text = """
❓ **Как пользоваться ботом:**

1. **➕ Добавить событие** - добавьте событие на конкретную дату
2. **📅 Расписание на дату** - посмотрите что запланировано на определенную дату
3. **📊 Расписание на неделю** - обзор всех событий на неделю
4. **🔍 Анализ** - получайте умные советы по вашему расписанию
5. **✏️ Редактировать** - измените время, описание или дату события
6. **📈 Статистика** - подробная аналитика вашего расписания
7. **🗑️ Очистить дату** - удалите все события на конкретную дату

**Команды:**
• `/add` - быстрое добавление события
• `/show` - показать расписание на неделю
• `/today` - что у вас сегодня
• `/help` - эта справка

**Формат добавления события:**
Дата Время Описание

**Примеры:**
• "2 сентября 13:55-15:50 Реабилитация и абилитация"
• "3 сентября 09:00-10:30 Математика, аудитория 101"
• "4 сентября 16:30-17:00 Работа в Т-Мобайл"

**Редактирование:**
• "время 14:00-15:30" - изменить время
• "описание Новая встреча" - изменить описание
• "дата 5 сентября" - переместить на другую дату

**Формат даты:**
• "2 сентября" (автоматически определится как 2025-09-02)
• "15 октября"
• "3 ноября"

Бот автоматически определит тип события (учебное/рабочее) и отсортирует по времени! ⏰
"""
        bot.edit_message_text(
            help_text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_back_keyboard()
        )
    
    elif data == "back_to_main":
        bot.edit_message_text(
            "🏠 **Главное меню**\n\n"
            "Выберите действие:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_main_keyboard()
        )

def main():
    """Главная функция"""
    logger.info("🚀 Запуск бота...")
    
    # Запускаем Flask в отдельном потоке для Render.com
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("🌐 Flask запущен в отдельном потоке")
    
    # Запускаем планировщик в отдельном потоке
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    logger.info("⏰ Планировщик запущен в отдельном потоке")
    
    # Запускаем бота
    try:
        logger.info("🤖 Бот запущен и готов к работе!")
        bot.polling(none_stop=True)
    except Exception as e:
        logger.error(f"❌ Ошибка запуска бота: {e}")
    finally:
        bot.stop_polling()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
