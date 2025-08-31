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
    
    def add_work_session(self, user_id: int, date_text: str, time_text: str, communications: int, session_type: str = "support") -> str:
        """Добавляет рабочую сессию с количеством коммуникаций"""
        if user_id not in self.schedules:
            self.schedules[user_id] = {}
        
        # Парсим дату
        date_key = self.parse_date(date_text)
        
        if date_key not in self.schedules[user_id]:
            self.schedules[user_id][date_key] = []
        
        # Генерируем уникальный ID
        import uuid
        session_id = str(uuid.uuid4())[:8]
        
        # Создаем рабочую сессию
        work_session = {
            'id': session_id,
            'time': time_text.strip(),
            'type': 'work_session',
            'communications': communications,
            'session_type': session_type,
            'productivity': communications / self._parse_hours(time_text) if self._parse_hours(time_text) > 0 else 0,
            'added_at': datetime.now().isoformat()
        }
        
        # Добавляем сессию и сортируем по времени
        self.schedules[user_id][date_key].append(work_session)
        self.schedules[user_id][date_key].sort(key=lambda x: x['time'])
        
        self.save_schedules()
        
        return f"✅ Рабочая сессия добавлена на {date_text} в {time_text}\n📊 Коммуникаций: {communications}\n🆔 ID: {session_id}"
    
    def _parse_hours(self, time_text: str) -> float:
        """Парсит время и возвращает количество часов"""
        try:
            # Формат: "09:00-17:00" или "9:00-17:00"
            parts = time_text.split('-')
            if len(parts) == 2:
                start_time = datetime.strptime(parts[0].strip(), '%H:%M')
                end_time = datetime.strptime(parts[1].strip(), '%H:%M')
                
                # Вычисляем разность
                duration = end_time - start_time
                hours = duration.total_seconds() / 3600
                return max(hours, 0.1)  # Минимум 0.1 часа
        except:
            pass
        return 1.0  # По умолчанию 1 час
    
    def get_work_statistics(self, user_id: int, period: str = "month") -> str:
        """Получает статистику по работе"""
        if user_id not in self.schedules:
            return "📝 У вас пока нет рабочих сессий."
        
        # Определяем период
        today = datetime.now()
        if period == "decade":
            # Текущая декада (1-10, 11-20, 21-31)
            day = today.day
            if day <= 10:
                start_date = today.replace(day=1)
                end_date = today.replace(day=10)
            elif day <= 20:
                start_date = today.replace(day=11)
                end_date = today.replace(day=20)
            else:
                start_date = today.replace(day=21)
                end_date = today.replace(day=31)
        elif period == "month":
            start_date = today.replace(day=1)
            end_date = today.replace(day=31)
        else:
            return "❌ Неизвестный период. Используйте 'decade' или 'month'"
        
        # Собираем статистику
        total_communications = 0
        total_hours = 0
        sessions_count = 0
        
        for date_key, events in self.schedules[user_id].items():
            try:
                date_obj = datetime.strptime(date_key, '%Y-%m-%d')
                if start_date <= date_obj <= end_date:
                    for event in events:
                        if event.get('type') == 'work_session':
                            total_communications += event.get('communications', 0)
                            total_hours += self._parse_hours(event.get('time', '1:00'))
                            sessions_count += 1
            except:
                pass
        
        if sessions_count == 0:
            return f"📊 За {period} у вас пока нет рабочих сессий."
        
        # Цели
        monthly_goal = 1000
        decade_goal = 300
        
        # Средняя производительность
        avg_productivity = total_communications / total_hours if total_hours > 0 else 0
        
        # Прогноз
        if period == "month":
            days_in_month = 31
            days_passed = min(today.day, days_in_month)
            progress_percent = (days_passed / days_in_month) * 100
            
            if progress_percent > 0:
                projected_monthly = (total_communications / progress_percent) * 100
            else:
                projected_monthly = 0
        else:
            projected_monthly = 0
        
        result = f"📊 **Статистика работы за {period}:**\n\n"
        result += f"📈 **Показатели:**\n"
        result += f"• Всего коммуникаций: {total_communications}\n"
        result += f"• Рабочих сессий: {sessions_count}\n"
        result += f"• Общее время: {total_hours:.1f} часов\n"
        result += f"• Средняя производительность: {avg_productivity:.1f} комм/час\n\n"
        
        # Анализ целей
        if period == "decade":
            result += f"🎯 **Цель декады:** {decade_goal} коммуникаций\n"
            if total_communications >= decade_goal:
                result += f"✅ Цель достигнута! Отлично работаете!\n"
            else:
                remaining = decade_goal - total_communications
                result += f"📝 Осталось: {remaining} коммуникаций\n"
        elif period == "month":
            result += f"🎯 **Цель месяца:** {monthly_goal} коммуникаций\n"
            if total_communications >= monthly_goal:
                result += f"✅ Цель достигнута! Вы молодец!\n"
            else:
                remaining = monthly_goal - total_communications
                result += f"📝 Осталось: {remaining} коммуникаций\n"
            
            if projected_monthly > 0:
                result += f"📊 Прогноз на месяц: {projected_monthly:.0f} коммуникаций\n"
        
        # Рекомендации
        result += "\n💡 **Рекомендации:**\n"
        if avg_productivity > 15:
            result += "• Высокая производительность! Не забудьте про отдых.\n"
        elif avg_productivity < 10:
            result += "• Можно увеличить темп, но не переусердствуйте.\n"
        else:
            result += "• Оптимальная производительность! Держите темп.\n"
        
        if total_hours > 160:  # 8 часов * 20 дней
            result += "• Много рабочих часов! Планируйте отдых.\n"
        
        return result
    
    def get_smart_work_schedule(self, user_id: int, target_communications: int, date_text: str) -> str:
        """Генерирует умное рабочее расписание"""
        if user_id not in self.schedules:
            self.schedules[user_id] = {}
        
        date_key = self.parse_date(date_text)
        
        # Проверяем учебное расписание на эту дату
        study_events = []
        if date_key in self.schedules[user_id]:
            study_events = [event for event in self.schedules[user_id][date_key] if event.get('type') == 'study']
        
        # Рассчитываем оптимальное время работы
        target_hours = target_communications / 13  # 13 комм/час
        available_hours = 8  # Максимум 8 часов в день
        
        # Учитываем учебные занятия
        study_hours = 0
        for event in study_events:
            study_hours += self._parse_hours(event.get('time', '1:00'))
        
        available_hours -= study_hours
        
        if available_hours < target_hours:
            result = f"⚠️ **Внимание:** На {date_text} недостаточно времени!\n\n"
            result += f"📚 Учебные занятия: {study_hours:.1f} часов\n"
            result += f"⏰ Доступно для работы: {available_hours:.1f} часов\n"
            result += f"📊 Нужно для {target_communications} комм: {target_hours:.1f} часов\n\n"
            result += f"💡 **Рекомендации:**\n"
            result += f"• Перенесите часть работы на другой день\n"
            result += f"• Увеличьте производительность до {target_communications/available_hours:.1f} комм/час\n"
            result += f"• Сократите учебные занятия\n"
        else:
            result = f"✅ **Оптимальное расписание на {date_text}:**\n\n"
            result += f"📚 Учебные занятия: {study_hours:.1f} часов\n"
            result += f"💼 Рабочее время: {target_hours:.1f} часов\n"
            result += f"⏰ Доступно: {available_hours:.1f} часов\n\n"
            
            # Генерируем временные слоты
            if study_events:
                result += f"📅 **Рекомендуемый порядок:**\n"
                for i, event in enumerate(study_events, 1):
                    result += f"{i}. {event['time']} - {event['activity']}\n"
                result += f"\n💼 **Рабочие сессии:**\n"
            
            # Разбиваем работу на сессии
            sessions = self._split_work_sessions(target_hours, study_events)
            for i, session in enumerate(sessions, 1):
                result += f"{i}. {session['time']} - {session['communications']} коммуникаций\n"
            
            result += f"\n💡 **Советы:**\n"
            result += f"• Делайте перерывы каждые 2 часа\n"
            result += f"• Планируйте сложные задачи на пик продуктивности\n"
            result += f"• Не забудьте про отдых между сессиями\n"
        
        return result
    
    def _split_work_sessions(self, total_hours: float, study_events: list) -> list:
        """Разбивает рабочее время на оптимальные сессии"""
        sessions = []
        
        # Оптимальная длительность сессии: 2-3 часа
        if total_hours <= 2:
            sessions.append({
                'time': '09:00-11:00',
                'communications': int(total_hours * 13)
            })
        elif total_hours <= 4:
            sessions.extend([
                {'time': '09:00-11:00', 'communications': 26},
                {'time': '14:00-16:00', 'communications': int((total_hours - 2) * 13)}
            ])
        else:
            sessions.extend([
                {'time': '09:00-11:00', 'communications': 26},
                {'time': '14:00-16:00', 'communications': 26},
                {'time': '16:30-18:30', 'communications': int((total_hours - 4) * 13)}
            ])
        
        return sessions

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
        InlineKeyboardButton("💼 Рабочая сессия", callback_data="add_work_session"),
        InlineKeyboardButton("📊 Статистика работы", callback_data="work_stats")
    )
    keyboard.add(
        InlineKeyboardButton("🤖 ИИ-планировщик", callback_data="ai_planner"),
        InlineKeyboardButton("📚 Умные напоминания", callback_data="smart_reminders")
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

Я ваш персональный ИИ-помощник по расписанию! 🗓️🤖

Что я умею:
• ➕ Добавлять события на конкретные даты
• 📅 Показывать расписание на дату/неделю
• 🔍 Анализировать ваше расписание
• ✏️ Редактировать события
• 📈 Подробная статистика
• 💼 Рабочие сессии Т-Мобайл с подсчетом коммуникаций
• 🤖 ИИ-планировщик работы с учетом учебы
• 📚 Пошаговые помощники для добавления
• 🔔 Ежедневные напоминания
• 💡 Умные советы по оптимизации

**Цели работы Т-Мобайл:**
🎯 Месяц: 1000 коммуникаций
🎯 Декада: 300 коммуникаций
📊 Производительность: 13 комм/час

Примеры использования:
• "2 сентября 13:55-15:50 Реабилитация и абилитация"
• "2 сентября 09:00-17:00 104" (рабочая сессия)
• "/ai_plan 100 2 сентября" (ИИ-планировщик)

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
7. **💼 Рабочая сессия** - добавьте рабочую сессию с количеством коммуникаций
8. **📊 Статистика работы** - анализ работы по декадам и месяцам
9. **🤖 ИИ-планировщик** - умное планирование работы с учетом учебы
10. **📚 Умные напоминания** - пошаговое добавление учебы и работы
11. **🗑️ Очистить дату** - удалите все события на конкретную дату

**Команды:**
• `/add` - быстрое добавление события
• `/show` - показать расписание на неделю
• `/today` - что у вас сегодня
• `/work_stats` - статистика работы (за месяц или декаду)
• `/ai_plan КОЛИЧЕСТВО_КОММ ДАТА` - ИИ-планировщик работы
• `/help` - эта справка

**Формат добавления события:**
Дата Время Описание

**Примеры:**
• "2 сентября 13:55-15:50 Реабилитация и абилитация"
• "3 сентября 09:00-10:30 Математика, аудитория 101"
• "4 сентября 16:30-17:00 Работа в Т-Мобайл"

**Рабочие сессии (Т-Мобайл):**
Дата Время Количество_коммуникаций

**Примеры:**
• "2 сентября 09:00-17:00 104"
• "3 сентября 14:00-18:00 52"

**ИИ-планировщик:**
Количество_коммуникаций Дата

**Примеры:**
• "100 2 сентября"
• "150 5 сентября"

**Редактирование:**
• "время 14:00-15:30" - изменить время
• "описание Новая встреча" - изменить описание
• "дата 5 сентября" - переместить на другую дату

**Формат даты:**
• "2 сентября" (автоматически определится как 2025-09-02)
• "15 октября"
• "3 ноября"

**Цели работы Т-Мобайл:**
• 🎯 Месяц: 1000 коммуникаций
• 🎯 Декада: 300 коммуникаций
• 📊 Производительность: 13 комм/час

Бот автоматически определит тип события, отсортирует по времени и поможет достичь целей! ⏰🚀
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

@bot.message_handler(commands=['work_stats'])
def cmd_work_stats(message: Message):
    """Обработчик команды /work_stats - статистика работы"""
    user_id = message.from_user.id
    
    # Парсим аргументы команды
    args = message.text.split()
    period = "month"  # По умолчанию месяц
    
    if len(args) > 1:
        if args[1].lower() in ['decade', 'декада']:
            period = "decade"
        elif args[1].lower() in ['month', 'месяц']:
            period = "month"
    
    result = schedule_manager.get_work_statistics(user_id, period)
    bot.reply_to(message, result, reply_markup=get_main_keyboard())
    logger.info(f"📊 Пользователь {user_id} запросил статистику работы за {period}")

@bot.message_handler(commands=['ai_plan'])
def cmd_ai_plan(message: Message):
    """Обработчик команды /ai_plan - ИИ-планировщик"""
    user_id = message.from_user.id
    
    # Парсим аргументы: /ai_plan 100 2 сентября
    args = message.text.split()
    if len(args) >= 3:
        try:
            target_communications = int(args[1])
            date_text = " ".join(args[2:])
            result = schedule_manager.get_smart_work_schedule(user_id, target_communications, date_text)
            bot.reply_to(message, result, reply_markup=get_main_keyboard())
            logger.info(f"🤖 Пользователь {user_id} использовал ИИ-планировщик для {target_communications} комм на {date_text}")
        except ValueError:
            bot.reply_to(
                message,
                "❌ Неверный формат! Используйте:\n"
                "/ai_plan КОЛИЧЕСТВО_КОММУНИКАЦИЙ ДАТА\n\n"
                "Пример: /ai_plan 100 2 сентября",
                reply_markup=get_main_keyboard()
            )
    else:
        bot.reply_to(
            message,
            "❌ Неверный формат! Используйте:\n"
            "/ai_plan КОЛИЧЕСТВО_КОММУНИКАЦИЙ ДАТА\n\n"
            "Пример: /ai_plan 100 2 сентября",
            reply_markup=get_main_keyboard()
        )

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
            
        elif state == 'waiting_for_work_session':
            # Парсим рабочую сессию: "2 сентября 09:00-17:00 104"
            try:
                parts = message.text.strip().split()
                if len(parts) >= 4:
                    # Первые 2 части - дата (например: "2 сентября")
                    date_part = f"{parts[0]} {parts[1]}"
                    # 3-я часть - время (например: "09:00-17:00")
                    time_part = parts[2]
                    # 4-я часть - количество коммуникаций
                    communications = int(parts[3])
                    
                    result = schedule_manager.add_work_session(user_id, date_part, time_part, communications)
                    bot.reply_to(message, result, reply_markup=get_main_keyboard())
                    logger.info(f"💼 Пользователь {user_id} добавил рабочую сессию: {date_part} {time_part} {communications} комм")
                else:
                    bot.reply_to(message, 
                        "❌ Неверный формат! Используйте:\n"
                        "Дата Время Количество_коммуникаций\n\n"
                        "Пример: '2 сентября 09:00-17:00 104'",
                        reply_markup=get_main_keyboard())
                    logger.warning(f"❌ Пользователь {user_id} ввел неверный формат рабочей сессии: {message.text}")
                    return
            except ValueError:
                bot.reply_to(message, 
                    "❌ Ошибка! Количество коммуникаций должно быть числом.\n\n"
                    "Пример: '2 сентября 09:00-17:00 104'",
                    reply_markup=get_main_keyboard())
                logger.error(f"❌ Ошибка при добавлении рабочей сессии пользователем {user_id}: неверное число")
                return
            except Exception as e:
                bot.reply_to(message, 
                    "❌ Ошибка при добавлении рабочей сессии. Проверьте формат:\n"
                    "Дата Время Количество_коммуникаций\n\n"
                    "Пример: '2 сентября 09:00-17:00 104'",
                    reply_markup=get_main_keyboard())
                logger.error(f"❌ Ошибка при добавлении рабочей сессии пользователем {user_id}: {e}")
                return
            finally:
                del user_states[user_id]
            
        elif state == 'waiting_for_ai_plan':
            # Парсим ИИ-план: "100 2 сентября"
            try:
                parts = message.text.strip().split()
                if len(parts) >= 2:
                    target_communications = int(parts[0])
                    date_text = " ".join(parts[1:])
                    
                    result = schedule_manager.get_smart_work_schedule(user_id, target_communications, date_text)
                    bot.reply_to(message, result, reply_markup=get_main_keyboard())
                    logger.info(f"🤖 Пользователь {user_id} использовал ИИ-планировщик для {target_communications} комм на {date_text}")
                else:
                    bot.reply_to(message, 
                        "❌ Неверный формат! Используйте:\n"
                        "Количество_коммуникаций Дата\n\n"
                        "Пример: '100 2 сентября'",
                        reply_markup=get_main_keyboard())
                    logger.warning(f"❌ Пользователь {user_id} ввел неверный формат для ИИ-планировщика: {message.text}")
                    return
            except ValueError:
                bot.reply_to(message, 
                    "❌ Ошибка! Количество коммуникаций должно быть числом.\n\n"
                    "Пример: '100 2 сентября'",
                    reply_markup=get_main_keyboard())
                logger.error(f"❌ Ошибка при использовании ИИ-планировщика пользователем {user_id}: неверное число")
                return
            except Exception as e:
                bot.reply_to(message, 
                    "❌ Ошибка при использовании ИИ-планировщика. Проверьте формат:\n"
                    "Количество_коммуникаций Дата\n\n"
                    "Пример: '100 2 сентября'",
                    reply_markup=get_main_keyboard())
                logger.error(f"❌ Ошибка при использовании ИИ-планировщика пользователем {user_id}: {e}")
                return
            finally:
                del user_states[user_id]
            
        elif state == 'waiting_for_study_date':
            # Шаг 1: Получили дату, теперь запрашиваем время
            user_states[user_id] = f'waiting_for_study_time_{message.text}'
            bot.reply_to(
                message,
                f"📚 **Шаг 2: Введите время**\n\n"
                f"Дата: {message.text}\n\n"
                f"Введите время в формате:\n"
                f"• 09:00-10:30\n"
                f"• 14:00-15:30\n"
                f"• 16:00-17:00",
                reply_markup=get_back_keyboard()
            )
            logger.info(f"📚 Пользователь {user_id} ввел дату для учебы: {message.text}")
            
        elif state.startswith('waiting_for_study_time_'):
            # Шаг 2: Получили время, теперь запрашиваем название предмета
            date_text = state.split('_', 3)[3]  # Извлекаем дату из состояния
            user_states[user_id] = f'waiting_for_study_subject_{date_text}_{message.text}'
            bot.reply_to(
                message,
                f"📚 **Шаг 3: Введите название предмета**\n\n"
                f"Дата: {date_text}\n"
                f"Время: {message.text}\n\n"
                f"Введите название предмета и дополнительную информацию:\n"
                f"• Математика, аудитория 101\n"
                f"• Физика, лабораторная работа\n"
                f"• Английский язык",
                reply_markup=get_back_keyboard()
            )
            logger.info(f"📚 Пользователь {user_id} ввел время для учебы: {message.text}")
            
        elif state.startswith('waiting_for_study_subject_'):
            # Шаг 3: Получили название предмета, добавляем событие
            parts = state.split('_', 3)[3:]  # Извлекаем дату и время
            if len(parts) >= 2:
                date_text = parts[0]
                time_text = parts[1]
                subject = message.text
                
                result = schedule_manager.add_event(user_id, date_text, time_text, subject, "study")
                bot.reply_to(message, result, reply_markup=get_main_keyboard())
                logger.info(f"📚 Пользователь {user_id} добавил учебное событие: {date_text} {time_text} {subject}")
            else:
                bot.reply_to(message, "❌ Ошибка! Попробуйте снова.", reply_markup=get_main_keyboard())
            
            del user_states[user_id]
            
        elif state == 'waiting_for_work_date':
            # Шаг 1: Получили дату, теперь запрашиваем время
            user_states[user_id] = f'waiting_for_work_time_{message.text}'
            bot.reply_to(
                message,
                f"💼 **Шаг 2: Введите время**\n\n"
                f"Дата: {message.text}\n\n"
                f"Введите время в формате:\n"
                f"• 09:00-17:00\n"
                f"• 14:00-18:00\n"
                f"• 10:00-16:00",
                reply_markup=get_back_keyboard()
            )
            logger.info(f"💼 Пользователь {user_id} ввел дату для работы: {message.text}")
            
        elif state.startswith('waiting_for_work_time_'):
            # Шаг 2: Получили время, теперь запрашиваем описание работы
            date_text = state.split('_', 3)[3]  # Извлекаем дату из состояния
            user_states[user_id] = f'waiting_for_work_description_{date_text}_{message.text}'
            bot.reply_to(
                message,
                f"💼 **Шаг 3: Введите описание работы**\n\n"
                f"Дата: {date_text}\n"
                f"Время: {message.text}\n\n"
                f"Введите описание работы:\n"
                f"• Поддержка клиентов Т-Мобайл\n"
                f"• Обработка заявок\n"
                f"• Консультации по тарифам",
                reply_markup=get_back_keyboard()
            )
            logger.info(f"💼 Пользователь {user_id} ввел время для работы: {message.text}")
            
        elif state.startswith('waiting_for_work_description_'):
            # Шаг 3: Получили описание работы, добавляем событие
            parts = state.split('_', 3)[3:]  # Извлекаем дату и время
            if len(parts) >= 2:
                date_text = parts[0]
                time_text = parts[1]
                description = message.text
                
                result = schedule_manager.add_event(user_id, date_text, time_text, description, "work")
                bot.reply_to(message, result, reply_markup=get_main_keyboard())
                logger.info(f"💼 Пользователь {user_id} добавил рабочее событие: {date_text} {time_text} {description}")
            else:
                bot.reply_to(message, "❌ Ошибка! Попробуйте снова.", reply_markup=get_main_keyboard())
            
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
    
    elif data == "add_work_session":
        user_states[user_id] = 'waiting_for_work_session'
        bot.edit_message_text(
            "💼 **Добавление рабочей сессии**\n\n"
            "Введите рабочую сессию в формате:\n"
            "Дата Время Количество_коммуникаций\n\n"
            "Примеры:\n"
            "• 2 сентября 09:00-17:00 104\n"
            "• 3 сентября 14:00-18:00 52\n"
            "• 4 сентября 10:00-16:00 78\n\n"
            "Бот автоматически рассчитает производительность!",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_back_keyboard()
        )
        logger.info(f"💼 Пользователь {user_id} выбрал добавление рабочей сессии")
    
    elif data == "work_stats":
        # Показываем меню выбора периода
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("📊 За декаду", callback_data="stats_decade"),
            InlineKeyboardButton("📊 За месяц", callback_data="stats_month")
        )
        keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main"))
        
        bot.edit_message_text(
            "📊 **Статистика работы**\n\n"
            "Выберите период для анализа:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard
        )
        logger.info(f"📊 Пользователь {user_id} выбрал статистику работы")
    
    elif data == "ai_planner":
        user_states[user_id] = 'waiting_for_ai_plan'
        bot.edit_message_text(
            "🤖 **ИИ-планировщик работы**\n\n"
            "Введите цель и дату в формате:\n"
            "Количество_коммуникаций Дата\n\n"
            "Примеры:\n"
            "• 100 2 сентября\n"
            "• 150 5 сентября\n"
            "• 80 10 сентября\n\n"
            "ИИ учтет ваше учебное расписание и предложит оптимальное рабочее время!",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_back_keyboard()
        )
        logger.info(f"🤖 Пользователь {user_id} выбрал ИИ-планировщик")
    
    elif data == "smart_reminders":
        # Показываем меню умных напоминаний
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("📚 Добавить учебу", callback_data="add_study_guided"),
            InlineKeyboardButton("💼 Добавить работу", callback_data="add_work_guided")
        )
        keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main"))
        
        bot.edit_message_text(
            "📚 **Умные напоминания**\n\n"
            "Выберите тип расписания для пошагового добавления:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard
        )
        logger.info(f"📚 Пользователь {user_id} выбрал умные напоминания")
    
    elif data == "stats_decade":
        result = schedule_manager.get_work_statistics(user_id, "decade")
        bot.edit_message_text(
            result,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_back_keyboard()
        )
        logger.info(f"📊 Пользователь {user_id} запросил статистику за декаду")
    
    elif data == "stats_month":
        result = schedule_manager.get_work_statistics(user_id, "month")
        bot.edit_message_text(
            result,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_back_keyboard()
        )
        logger.info(f"📊 Пользователь {user_id} запросил статистику за месяц")
    
    elif data == "add_study_guided":
        user_states[user_id] = 'waiting_for_study_date'
        bot.edit_message_text(
            "📚 **Пошаговое добавление учебы**\n\n"
            "Шаг 1: Введите дату\n\n"
            "Примеры:\n"
            "• 2 сентября\n"
            "• 15 октября\n"
            "• 3 ноября",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_back_keyboard()
        )
        logger.info(f"📚 Пользователь {user_id} начал пошаговое добавление учебы")
    
    elif data == "add_work_guided":
        user_states[user_id] = 'waiting_for_work_date'
        bot.edit_message_text(
            "💼 **Пошаговое добавление работы**\n\n"
            "Шаг 1: Введите дату\n\n"
            "Примеры:\n"
            "• 2 сентября\n"
            "• 15 октября\n"
            "• 3 ноября",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_back_keyboard()
        )
        logger.info(f"💼 Пользователь {user_id} начал пошаговое добавление работы")
    
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
