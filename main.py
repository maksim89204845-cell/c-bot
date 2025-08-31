import os
import logging
from datetime import datetime, timedelta
import json
from typing import Dict, List, Optional
import threading
from flask import Flask, request, jsonify
import schedule
import time
import uuid
import signal
import sys

# Импорты для telebot (pyTelegramBotAPI)
try:
    import telebot
    from telebot import TeleBot
    from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery
    print("✅ pyTelegramBotAPI успешно импортирован")
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
                
                # Валидация дня
                if day < 1 or day > 31:
                    logger.warning(f"⚠️ Некорректный день: {day}")
                    return date_text
                
                month_name = parts[1].lower()
                
                if month_name in months:
                    month = months[month_name]
                    
                    # Валидация конкретных месяцев
                    if month == 2 and day > 29:  # Февраль
                        logger.warning(f"⚠️ Некорректный день для февраля: {day}")
                        return date_text
                    elif month in [4, 6, 9, 11] and day > 30:  # 30-дневные месяцы
                        logger.warning(f"⚠️ Некорректный день для {month_name}: {day}")
                        return date_text
                    
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
        
        # Валидация времени
        if not self._validate_time_format(time_text):
            return f"❌ Неправильный формат времени: {time_text}\nИспользуйте формат: 13:55-15:35"
        
        # Парсим дату
        date_key = self.parse_date(date_text)
        
        if date_key not in self.schedules[user_id]:
            self.schedules[user_id][date_key] = []
        
        # Генерируем уникальный ID
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
    
    def _validate_time_format(self, time_text: str) -> bool:
        """Проверяет корректность формата времени"""
        try:
            # Ожидаемый формат: "13:55-15:35"
            if '-' not in time_text:
                return False
            
            start_time, end_time = time_text.split('-')
            
            # Проверяем формат времени (HH:MM)
            for time_part in [start_time.strip(), end_time.strip()]:
                if ':' not in time_part:
                    return False
                
                hour, minute = time_part.split(':')
                hour_int = int(hour)
                minute_int = int(minute)
                
                if hour_int < 0 or hour_int > 23 or minute_int < 0 or minute_int > 59:
                    return False
            
            return True
        except:
            return False
    
    def get_date_schedule(self, user_id: int, date_text: str) -> str:
        """Получает расписание на конкретную дату"""
        if user_id not in self.schedules:
            return "📅 У вас пока нет расписаний. Добавьте первое событие!"
        
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
        if user_id not in self.schedules or not self.schedules[user_id]:
            return "📅 На этой неделе у вас нет запланированных событий."
        
        result = "📅 Расписание на неделю:\n\n"
        
        # Сортируем даты
        sorted_dates = sorted(self.schedules[user_id].keys())
        
        for date_key in sorted_dates:
            events = self.schedules[user_id][date_key]
            if events:
                # Словарь для русских названий месяцев
                months_ru = {
                    1: 'января', 2: 'февраля', 3: 'марта', 4: 'апреля',
                    5: 'мая', 6: 'июня', 7: 'июля', 8: 'августа',
                    9: 'сентября', 10: 'октября', 11: 'ноября', 12: 'декабря'
                }
                
                # Преобразуем дату в читаемый формат
                try:
                    date_obj = datetime.strptime(date_key, '%Y-%m-%d')
                    day = date_obj.day
                    month = months_ru.get(date_obj.month, str(date_obj.month))
                    date_display = f"{day} {month}"
                except (ValueError, TypeError) as e:
                    logger.warning(f"⚠️ Ошибка парсинга даты '{date_key}': {e}")
                    date_display = date_key
                except Exception as e:
                    logger.warning(f"⚠️ Неожиданная ошибка при форматировании даты '{date_key}': {e}")
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
        
        if not user_schedules:
            return "📝 У вас пока нет расписаний. Добавьте их для получения анализа!"
        
        analysis = "🔍 Анализ вашего расписания:\n\n"
        
        # Анализ по типам событий
        study_count = 0
        work_count = 0
        total_events = 0
        
        for date_key, events in user_schedules.items():
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
        
        # Словарь для русских названий дней недели
        weekdays_ru = {
            'Monday': 'Понедельник',
            'Tuesday': 'Вторник',
            'Wednesday': 'Среда',
            'Thursday': 'Четверг',
            'Friday': 'Пятница',
            'Saturday': 'Суббота',
            'Sunday': 'Воскресенье'
        }
        
        # Анализ по дням недели
        weekday_stats = {}
        for date_key, events in user_schedules.items():
            try:
                date_obj = datetime.strptime(date_key, '%Y-%m-%d')
                english_weekday = date_obj.strftime('%A')
                russian_weekday = weekdays_ru.get(english_weekday, english_weekday)
                
                if russian_weekday not in weekday_stats:
                    weekday_stats[russian_weekday] = 0
                weekday_stats[russian_weekday] += len(events)
            except (ValueError, TypeError) as e:
                logger.warning(f"⚠️ Ошибка парсинга даты '{date_key}': {e}")
                continue
            except Exception as e:
                logger.warning(f"⚠️ Неожиданная ошибка при анализе даты '{date_key}': {e}")
                continue
        
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
    
    def get_smart_work_schedule(self, user_id: int, current_communications: int) -> str:
        """Генерирует умное рабочее расписание на основе текущих коммуникаций"""
        try:
            # Определяем текущий месяц и декаду
            now = datetime.now()
            current_month = now.month
            current_day = now.day
            
            # Цели
            monthly_goal = 1000
            decade_goal = 300
            
            # Определяем декаду (1-10, 11-20, 21-31)
            if current_day <= 10:
                decade = 1
                decade_start = 1
                decade_end = 10
            elif current_day <= 20:
                decade = 2
                decade_start = 11
                decade_end = 20
            else:
                decade = 3
                decade_start = 21
                decade_end = 31
            
            # Рассчитываем оставшиеся дни
            days_in_month = (now.replace(month=now.month % 12 + 1, day=1) - timedelta(days=1)).day
            remaining_days_in_month = days_in_month - current_day + 1
            remaining_days_in_decade = decade_end - current_day + 1
            
            # Рассчитываем необходимые коммуникации
            remaining_monthly = monthly_goal - current_communications
            remaining_decade = decade_goal - current_communications
            
            # Используем более критичную цель
            if remaining_decade > 0:
                target_communications = remaining_decade
                target_period = f"декаду (до {decade_end} числа)"
                target_days = remaining_days_in_decade
            else:
                target_communications = remaining_monthly
                target_period = f"месяц (до конца месяца)"
                target_days = remaining_days_in_month
            
            # Автоматическое планирование рабочей смены
            auto_plan = self.auto_plan_work_shift(user_id, target_communications)
            
            result = f"🤖 ИИ-планировщик для работы:\n\n"
            result += f"📊 Текущий прогресс: {current_communications} коммуникаций\n"
            result += f"🎯 Цель на {target_period}: {target_communications} коммуникаций\n"
            result += f"⏰ Осталось дней: {target_days}\n"
            result += f"📈 Нужно в день: {target_communications / target_days:.1f}\n\n"
            
            result += f"🚀 Автоматический план:\n{auto_plan}"
            
            return result
            
        except (ValueError, TypeError) as e:
            logger.error(f"❌ Ошибка валидации в ИИ-планировщике: {e}")
            return f"❌ Ошибка валидации данных: {e}"
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка в ИИ-планировщике: {e}")
            return f"❌ Неожиданная ошибка: {e}"
    
    def auto_plan_work_shift(self, user_id: int, target_communications: int) -> str:
        """Автоматически планирует оптимальную рабочую смену"""
        try:
            # Проверяем валидность target_communications
            if target_communications <= 0:
                return "❌ Некорректная цель: количество коммуникаций должно быть больше 0"
            
            # Словарь для русских названий дней недели (выносим за цикл)
            weekdays_ru = {
                'Monday': 'Понедельник',
                'Tuesday': 'Вторник',
                'Wednesday': 'Среда',
                'Thursday': 'Четверг',
                'Friday': 'Пятница',
                'Saturday': 'Суббота',
                'Sunday': 'Воскресенье'
            }
            
            # Находим свободные слоты на ближайшие 7 дней
            available_slots = []
            
            for i in range(7):
                check_date = (datetime.now() + timedelta(days=i)).strftime('%Y-%m-%d')
                
                # Проверяем существующие события
                existing_events = self.schedules.get(user_id, {}).get(check_date, [])
                
                # Ищем свободные 4-часовые слоты
                for hour in range(9, 18):  # 9:00 - 18:00
                    slot_start = f"{hour:02d}:00"
                    slot_end = f"{hour + 4:02d}:00"
                    
                    # Проверяем конфликты
                    conflict = False
                    for event in existing_events:
                        event_start = event.get('time', '').split('-')[0].strip()
                        event_end = event.get('time', '').split('-')[-1].strip()
                        
                        # Простая проверка пересечения времени
                        if (slot_start < event_end and slot_end > event_start):
                            conflict = True
                            break
                    
                    if not conflict:
                        # Получаем русское название дня недели
                        english_day = (datetime.now() + timedelta(days=i)).strftime('%A')
                        russian_day = weekdays_ru.get(english_day, english_day)
                        
                        available_slots.append({
                            'date': check_date,
                            'start': slot_start,
                            'end': slot_end,
                            'day_name': russian_day
                        })
            
            if not available_slots:
                return "❌ Нет свободных слотов на ближайшие 7 дней"
            
            # Выбираем лучший слот (приоритет: сегодня, завтра, затем по дням)
            best_slot = available_slots[0]
            
            # Рассчитываем возможные коммуникации (13 в час)
            hours = 4
            possible_communications = int(hours * 13)
            
            result = f"📅 Рекомендуемая смена:\n"
            result += f"• Дата: {best_slot['day_name']} ({best_slot['date']})\n"
            result += f"• Время: {best_slot['start']} - {best_slot['end']}\n"
            result += f"• Длительность: {hours} часа\n"
            result += f"• Ожидаемые коммуникации: {possible_communications}\n"
            result += f"• Прогресс к цели: {possible_communications / target_communications * 100:.1f}%\n\n"
            
            if possible_communications >= target_communications:
                result += "✅ Эта смена поможет достичь цели!"
            else:
                result += f"⚠️ Нужно еще {target_communications - possible_communications} коммуникаций"
            
            return result
            
        except (ValueError, TypeError) as e:
            logger.error(f"❌ Ошибка валидации в авто-планировании: {e}")
            return f"❌ Ошибка валидации данных: {e}"
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка в авто-планировании: {e}")
            return f"❌ Неожиданная ошибка: {e}"
    


# Инициализация менеджера расписания
schedule_manager = ScheduleManager()

# Получение токена бота
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не найден в переменных окружения!")
    exit(1)

# Инициализация бота
bot = telebot.TeleBot(BOT_TOKEN)

# Флаг для корректного завершения
shutdown_flag = False

def signal_handler(signum, frame):
    """Обработчик сигналов для корректного завершения"""
    global shutdown_flag
    logger.info(f"📡 Получен сигнал {signum}, завершаем работу...")
    shutdown_flag = True
    
    try:
        bot.stop_polling()
    except:
        pass
    
    sys.exit(0)

# Регистрируем обработчики сигналов
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Клавиатуры
def get_main_keyboard() -> InlineKeyboardMarkup:
    """Главная клавиатура"""
    keyboard = [
        [
            InlineKeyboardButton("➕ Добавить", callback_data="add_menu"),
            InlineKeyboardButton("📅 Показать", callback_data="show_menu")
        ],
        [
            InlineKeyboardButton("🤖 ИИ-планировщик", callback_data="ai_planner"),
            InlineKeyboardButton("📊 Статистика", callback_data="statistics")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_add_menu_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура меню добавления"""
    keyboard = [
        [
            InlineKeyboardButton("📚 Учеба", callback_data="add_study"),
            InlineKeyboardButton("💼 Работа", callback_data="add_work")
        ],
        [
            InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_show_menu_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура меню просмотра"""
    keyboard = [
        [
            InlineKeyboardButton("📅 На дату", callback_data="show_date"),
            InlineKeyboardButton("📊 На неделю", callback_data="show_week")
        ],
        [
            InlineKeyboardButton("🌅 Сегодня", callback_data="show_today"),
            InlineKeyboardButton("🤖 Рекомендации", callback_data="smart_recommendations")
        ],
        [
            InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_back_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой "Назад" """
    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")]]
    return InlineKeyboardMarkup(keyboard)

# Обработчики команд
@bot.message_handler(commands=['start'])
def cmd_start(message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    
    welcome_text = f"""
👋 Привет, {user_name}!

Я ваш персональный помощник по расписанию! 🗓️

Что я умею:
• 📚 Добавлять учебное расписание
• 💼 Добавлять рабочее расписание  
• 🤖 ИИ-планировщик для работы
• 📊 Анализ и рекомендации
• 🌅 Ежедневные напоминания

Выберите действие:
"""
    
    bot.reply_to(message, welcome_text, reply_markup=get_main_keyboard())
    logger.info(f"🚀 Пользователь {user_id} запустил бота")

@bot.message_handler(commands=['help'])
def cmd_help(message):
    """Обработчик команды /help"""
    help_text = """
❓ Как пользоваться ботом:

➕ Добавить:
• 📚 Учеба - введите предмет, дату и время
• 💼 Работа - введите описание, дату и время

📅 Показать:
• 📅 На дату - расписание на конкретную дату
• 📊 На неделю - расписание на всю неделю
• 🌅 Сегодня - что у вас сегодня
• 🤖 Рекомендации - советы по расписанию

🤖 ИИ-планировщик:
• Введите: ТЕКУЩИЙ_ПРОГРЕСС
• Пример: 250
• Бот автоматически рассчитает план

📊 Статистика:
• Общая статистика расписания
• Анализ загруженности

Примеры ввода:
• "Математика 2 сентября 13:55-15:35"
• "Встреча с клиентом 3 сентября 14:00-15:00"
• "250" (для ИИ-планировщика)
"""
    
    bot.reply_to(message, help_text, reply_markup=get_main_keyboard())

@bot.message_handler(commands=['recommendations'])
def cmd_recommendations(message):
    """Обработчик команды /recommendations"""
    user_id = message.from_user.id
    recommendations = schedule_manager.get_smart_recommendations(user_id)
    bot.reply_to(message, recommendations, reply_markup=get_main_keyboard())

@bot.message_handler(commands=['ai_plan'])
def cmd_ai_plan(message):
    """Обработчик команды /ai_plan"""
    user_id = message.from_user.id
    
    # Парсим аргументы
    args = message.text.split()[1:]
    if len(args) < 1:
        bot.reply_to(message, 
            "❌ Неправильный формат!\n\n"
            "Используйте: /ai_plan ТЕКУЩИЙ_ПРОГРЕСС\n"
            "Пример: /ai_plan 250",
            reply_markup=get_main_keyboard())
        return
    
    try:
        current_communications = int(args[0])
        if current_communications < 0:
            raise ValueError("Отрицательное число")
    except ValueError:
        bot.reply_to(message, 
            "❌ Неправильный формат числа!\n\n"
            "Введите положительное число коммуникаций.\n"
            "Пример: /ai_plan 250",
            reply_markup=get_main_keyboard())
        return
    
    # Получаем умное расписание
    smart_schedule = schedule_manager.get_smart_work_schedule(user_id, current_communications)
    bot.reply_to(message, smart_schedule, reply_markup=get_main_keyboard())
    
    logger.info(f"🤖 Пользователь {user_id} использовал ИИ-планировщик: {current_communications}")

# Обработчик текстовых сообщений
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    """Обработчик текстовых сообщений"""
    user_id = message.from_user.id
    text = message.text.strip()
    
    if user_id not in user_states:
        bot.reply_to(message, "Выберите действие в главном меню:", reply_markup=get_main_keyboard())
        return
    
    state = user_states[user_id]
    
    if state.startswith("waiting_for_study_subject_"):
        # Парсим дату и время из состояния
        try:
            state_parts = state.split('_', 4)
            if len(state_parts) >= 5:
                date_text = state_parts[3]
                time_text = state_parts[4]
                
                # Добавляем событие
                result = schedule_manager.add_event(user_id, date_text, time_text, text, "study")
                bot.reply_to(message, result, reply_markup=get_main_keyboard())
                
                # Очищаем состояние
                del user_states[user_id]
                logger.info(f"📚 Пользователь {user_id} добавил учебное событие: {text}")
            else:
                bot.reply_to(message, "❌ Ошибка! Попробуйте снова.", reply_markup=get_main_keyboard())
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга состояния: {e}")
            bot.reply_to(message, "❌ Ошибка! Попробуйте снова.", reply_markup=get_main_keyboard())
    
    elif state.startswith("waiting_for_work_description_"):
        # Парсим дату и время из состояния
        try:
            state_parts = state.split('_', 4)
            if len(state_parts) >= 5:
                date_text = state_parts[3]
                time_text = state_parts[4]
                
                # Добавляем событие
                result = schedule_manager.add_event(user_id, date_text, time_text, text, "work")
                bot.reply_to(message, result, reply_markup=get_main_keyboard())
                
                # Очищаем состояние
                del user_states[user_id]
                logger.info(f"💼 Пользователь {user_id} добавил рабочее событие: {text}")
            else:
                bot.reply_to(message, "❌ Ошибка! Попробуйте снова.", reply_markup=get_main_keyboard())
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга состояния: {e}")
            bot.reply_to(message, "❌ Ошибка! Попробуйте снова.", reply_markup=get_main_keyboard())
    
    elif state == "waiting_for_ai_plan":
        try:
            current_communications = int(text)
            if current_communications < 0:
                raise ValueError("Отрицательное число")
            
            # Получаем умное расписание
            smart_schedule = schedule_manager.get_smart_work_schedule(user_id, current_communications)
            bot.reply_to(message, smart_schedule, reply_markup=get_main_keyboard())
            
            # Очищаем состояние
            del user_states[user_id]
            logger.info(f"🤖 Пользователь {user_id} использовал ИИ-планировщик: {current_communications}")
            
        except ValueError:
            bot.reply_to(message, 
                "❌ Неправильный формат!\n\n"
                "Введите положительное число коммуникаций.\n"
                "Пример: 250",
                reply_markup=get_main_keyboard())
    
    elif state == "waiting_for_study_datetime":
        # Парсим дату и время
        try:
            parts = text.split()
            if len(parts) >= 3:
                day = parts[0]
                month = parts[1]
                time_range = parts[2]
                
                date_text = f"{day} {month}"
                time_text = time_range
                
                # Устанавливаем состояние ожидания предмета
                user_states[user_id] = f"waiting_for_study_subject_{date_text}_{time_text}"
                
                bot.reply_to(message, 
                    f"📚 Отлично! Дата: {date_text}, Время: {time_text}\n\n"
                    "Теперь введите название предмета:",
                    reply_markup=get_back_keyboard())
            else:
                bot.reply_to(message, 
                    "❌ Неправильный формат!\n\n"
                    "Используйте: 2 сентября 13:55-15:35",
                    reply_markup=get_back_keyboard())
        except Exception as e:
            bot.reply_to(message, 
                "❌ Ошибка! Попробуйте снова.",
                reply_markup=get_back_keyboard())
    
    elif state == "waiting_for_work_datetime":
        # Парсим дату и время
        try:
            parts = text.split()
            if len(parts) >= 3:
                day = parts[0]
                month = parts[1]
                time_range = parts[2]
                
                date_text = f"{day} {month}"
                time_text = time_range
                
                # Устанавливаем состояние ожидания описания работы
                user_states[user_id] = f"waiting_for_work_description_{date_text}_{time_text}"
                
                bot.reply_to(message, 
                    f"💼 Отлично! Дата: {date_text}, Время: {time_text}\n\n"
                    "Теперь введите описание работы:",
                    reply_markup=get_back_keyboard())
            else:
                bot.reply_to(message, 
                    "❌ Неправильный формат!\n\n"
                    "Используйте: 2 сентября 14:00-15:00",
                    reply_markup=get_back_keyboard())
        except Exception as e:
            bot.reply_to(message, 
                "❌ Ошибка! Попробуйте снова.",
                reply_markup=get_back_keyboard())
    
    elif state == "waiting_for_date":
        # Показываем расписание на указанную дату
        schedule_text = schedule_manager.get_date_schedule(user_id, text)
        bot.reply_to(message, schedule_text, reply_markup=get_main_keyboard())
        
        # Очищаем состояние
        del user_states[user_id]
        logger.info(f"📅 Пользователь {user_id} запросил расписание на дату: {text}")
    
    else:
        bot.reply_to(message, "Выберите действие в главном меню:", reply_markup=get_main_keyboard())

# Обработчик callback-запросов
@bot.callback_query_handler(func=lambda call: True)
def process_callback(call):
    """Обработчик нажатий на кнопки"""
    user_id = call.from_user.id
    data = call.data
    
    bot.answer_callback_query(call.id)
    
    if data == "add_menu":
        bot.edit_message_text(
            "➕ Выберите тип события для добавления:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=get_add_menu_keyboard()
        )
        logger.info(f"➕ Пользователь {user_id} открыл меню добавления")
    
    elif data == "show_menu":
        bot.edit_message_text(
            "📅 Выберите что показать:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=get_show_menu_keyboard()
        )
        logger.info(f"📅 Пользователь {user_id} открыл меню просмотра")
    
    elif data == "add_study":
        bot.edit_message_text(
            "📚 Добавление учебного события\n\n"
            "Введите дату и время в формате:\n"
            "2 сентября 13:55-15:35\n\n"
            "Затем введите название предмета:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=get_back_keyboard()
        )
        
        # Устанавливаем состояние ожидания даты и времени
        user_states[user_id] = "waiting_for_study_datetime"
        logger.info(f"📚 Пользователь {user_id} начал добавление учебного события")
    
    elif data == "add_work":
        bot.edit_message_text(
            "💼 Добавление рабочего события\n\n"
            "Введите дату и время в формате:\n"
            "2 сентября 14:00-15:00\n\n"
            "Затем введите описание работы:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=get_back_keyboard()
        )
        
        # Устанавливаем состояние ожидания даты и времени
        user_states[user_id] = "waiting_for_work_datetime"
        logger.info(f"💼 Пользователь {user_id} начал добавление рабочего события")
    
    elif data == "show_date":
        bot.edit_message_text(
            "📅 Введите дату в формате:\n"
            "2 сентября\n\n"
            "Или выберите действие:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=get_back_keyboard()
        )
        user_states[user_id] = "waiting_for_date"
    

    
    elif data == "show_week":
        schedule_text = schedule_manager.get_week_schedule(user_id)
        bot.edit_message_text(
            schedule_text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=get_back_keyboard()
        )
        logger.info(f"📊 Пользователь {user_id} запросил недельное расписание")
    
    elif data == "show_today":
        schedule_text = schedule_manager.get_today_schedule(user_id)
        bot.edit_message_text(
            schedule_text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=get_back_keyboard()
        )
        logger.info(f"🌅 Пользователь {user_id} запросил сегодняшнее расписание")
    
    elif data == "smart_recommendations":
        recommendations = schedule_manager.get_smart_recommendations(user_id)
        bot.edit_message_text(
            recommendations,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=get_back_keyboard()
        )
        logger.info(f"🤖 Пользователь {user_id} запросил рекомендации")
    
    elif data == "ai_planner":
        bot.edit_message_text(
            "🤖 ИИ-планировщик для работы\n\n"
            "Введите текущее количество коммуникаций:\n"
            "Пример: 250\n\n"
            "Бот автоматически рассчитает:\n"
            "• Оставшиеся цели\n"
            "• Оптимальное расписание\n"
            "• Рекомендации",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=get_back_keyboard()
        )
        user_states[user_id] = "waiting_for_ai_plan"
        logger.info(f"🤖 Пользователь {user_id} открыл ИИ-планировщик")
    
    elif data == "statistics":
        analysis = schedule_manager.analyze_schedule(user_id)
        bot.edit_message_text(
            analysis,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=get_back_keyboard()
        )
        logger.info(f"📊 Пользователь {user_id} запросил статистику")
    
    elif data == "back_to_main":
        bot.edit_message_text(
            "🏠 Главное меню\n\n"
            "Выберите действие:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=get_main_keyboard()
        )
        logger.info(f"🏠 Пользователь {user_id} вернулся в главное меню")

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

# Главная функция
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
    
    # Запускаем бота с автоматическим перезапуском
    max_retries = 5
    retry_count = 0
    
    while retry_count < max_retries and not shutdown_flag:
        try:
            logger.info(f"🤖 Попытка запуска бота #{retry_count + 1}")
            
            # Очищаем webhook перед запуском
            bot.remove_webhook()
            
            # Запускаем бота
            bot.polling(none_stop=True, interval=1, timeout=60)
            
        except Exception as e:
            if shutdown_flag:
                break
                
            retry_count += 1
            error_msg = str(e)
            
            if "409" in error_msg or "Conflict" in error_msg:
                logger.warning(f"⚠️ Конфликт экземпляров бота (попытка {retry_count}/{max_retries})")
                logger.info("🔄 Ожидание 30 секунд перед повторной попыткой...")
                
                # Проверяем флаг завершения каждые 5 секунд
                for i in range(6):
                    if shutdown_flag:
                        break
                    time.sleep(5)
                
                # Очищаем состояние бота
                try:
                    bot.stop_polling()
                except:
                    pass
                
            else:
                logger.error(f"❌ Критическая ошибка: {e}")
                if retry_count < max_retries:
                    logger.info(f"🔄 Перезапуск через 10 секунд... (попытка {retry_count}/{max_retries})")
                    
                    # Проверяем флаг завершения каждые 2 секунды
                    for i in range(5):
                        if shutdown_flag:
                            break
                        time.sleep(2)
                else:
                    logger.error("❌ Превышено максимальное количество попыток запуска")
                    break
    
    logger.error("❌ Бот не смог запуститься после всех попыток")
    bot.stop_polling()

if __name__ == '__main__':
    main()
