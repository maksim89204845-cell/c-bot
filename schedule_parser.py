import requests
import PyPDF2
import io
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional

class ScheduleParser:
    def __init__(self, google_drive_url: str):
        self.google_drive_url = google_drive_url
        self.schedule_data = {}
        self.last_update = None
        
    def download_pdf(self) -> Optional[bytes]:
        """Скачивает PDF с Google Drive"""
        try:
            # Преобразуем ссылку для прямого скачивания
            file_id = self.google_drive_url.split('/d/')[1].split('/')[0]
            direct_url = f"https://drive.google.com/uc?export=download&id={file_id}"
            
            response = requests.get(direct_url, timeout=30)
            response.raise_for_status()
            return response.content
        except Exception as e:
            print(f"Ошибка скачивания PDF: {e}")
            return None
    
    def extract_text_from_pdf(self, pdf_content: bytes) -> str:
        """Извлекает текст из PDF"""
        try:
            pdf_file = io.BytesIO(pdf_content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text()
            
            return text
        except Exception as e:
            print(f"Ошибка извлечения текста из PDF: {e}")
            return ""
    
    def parse_schedule(self, text: str) -> Dict:
        """Парсит расписание из текста"""
        schedule = {}
        
        # Отладочная информация
        print(f"=== ОТЛАДКА ПАРСИНГА ===")
        print(f"Длина текста: {len(text)}")
        print(f"Первые 500 символов: {text[:500]}")
        print(f"=== КОНЕЦ ОТЛАДКИ ===")
        
        # Разбиваем текст на строки
        lines = text.split('\n')
        
        current_date = None
        current_time = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Ищем дату (формат: DD.MM.YYYY)
            date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', line)
            if date_match:
                current_date = date_match.group(1)
                schedule[current_date] = {}
                print(f"Найдена дата: {current_date}")
                continue
            
            # Ищем время (формат: HH:MM-HH:MM)
            time_match = re.search(r'(\d{2}:\d{2})-(\d{2}:\d{2})', line)
            if time_match:
                current_time = f"{time_match.group(1)}-{time_match.group(2)}"
                if current_date and current_time:
                    schedule[current_date][current_time] = {
                        'subject': '',
                        'instructor': '',
                        'auditorium': ''
                    }
                    print(f"Найдено время: {current_time} для даты {current_date}")
                continue
            
            # Ищем информацию о занятии для группы 302Ф
            if current_date and current_time and '302' in line:
                print(f"Найдена строка с 302: {line}")
                # Извлекаем предмет, преподавателя и аудиторию
                parts = line.split()
                if len(parts) >= 3:
                    schedule[current_date][current_time] = {
                        'subject': ' '.join(parts[:-2]),
                        'instructor': parts[-2],
                        'auditorium': parts[-1]
                    }
                    print(f"Извлечено: предмет={parts[:-2]}, преподаватель={parts[-2]}, аудитория={parts[-1]}")
        
        print(f"Итоговое расписание: {schedule}")
        return schedule
    
    def get_schedule_for_date(self, target_date: str) -> Dict:
        """Получает расписание на конкретную дату"""
        if not self.schedule_data:
            self.update_schedule()
        
        return self.schedule_data.get(target_date, {})
    
    def get_schedule_for_tomorrow(self) -> Dict:
        """Получает расписание на завтра"""
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%d.%m.%Y')
        return self.get_schedule_for_date(tomorrow)
    
    def get_schedule_for_week(self) -> Dict:
        """Получает расписание на неделю"""
        if not self.schedule_data:
            self.update_schedule()
        
        return self.schedule_data
    
    def update_schedule(self) -> bool:
        """Обновляет расписание"""
        try:
            pdf_content = self.download_pdf()
            if pdf_content:
                text = self.extract_text_from_pdf(pdf_content)
                self.schedule_data = self.parse_schedule(text)
                self.last_update = datetime.now()
                return True
            return False
        except Exception as e:
            print(f"Ошибка обновления расписания: {e}")
            return False
    
    def format_schedule_message(self, schedule: Dict, date: str = None) -> str:
        """Форматирует расписание для отправки в Telegram"""
        if not schedule:
            return "Расписание не найдено или произошла ошибка при загрузке."
        
        if date:
            # Расписание на конкретную дату
            message = f"📅 Расписание на {date}:\n\n"
            for time, lesson in schedule.items():
                if lesson.get('subject'):
                    message += f"🕐 {time}\n"
                    message += f"📚 {lesson['subject']}\n"
                    message += f"👨‍🏫 {lesson['instructor']}\n"
                    message += f"🏢 {lesson['auditorium']}\n"
                    message += "─" * 30 + "\n"
                else:
                    message += f"🕐 {time} - Аудит.\n"
                    message += "─" * 30 + "\n"
        else:
            # Расписание на неделю
            message = "📅 Расписание на неделю:\n\n"
            for date, day_schedule in schedule.items():
                message += f"📆 {date}\n"
                for time, lesson in day_schedule.items():
                    if lesson.get('subject'):
                        message += f"🕐 {time} - {lesson['subject']} ({lesson['instructor']}, {lesson['auditorium']})\n"
                    else:
                        message += f"🕐 {time} - Аудит.\n"
                message += "─" * 30 + "\n"
        
        if self.last_update:
            message += f"\n🔄 Последнее обновление: {self.last_update.strftime('%d.%m.%Y %H:%M')}"
        
        return message
    
    def split_long_message(self, message: str, max_length: int = 4000) -> List[str]:
        """Разбивает длинное сообщение на части"""
        if len(message) <= max_length:
            return [message]
        
        parts = []
        lines = message.split('\n')
        current_part = ""
        
        for line in lines:
            if len(current_part + line + '\n') > max_length:
                if current_part:
                    parts.append(current_part.strip())
                    current_part = line + '\n'
                else:
                    # Одна строка слишком длинная
                    parts.append(line[:max_length-3] + "...")
            else:
                current_part += line + '\n'
        
        if current_part:
            parts.append(current_part.strip())
        
        return parts
    
    def format_week_schedule_messages(self, schedule: Dict) -> List[str]:
        """Форматирует расписание на неделю с разбивкой на сообщения"""
        if not schedule:
            return ["📅 Расписание на неделю не найдено."]
        
        # Создаем отдельное сообщение для каждого дня
        messages = []
        
        for date, day_schedule in schedule.items():
            day_message = f"📅 Расписание на {date}:\n\n"
            
            for time, lesson in day_schedule.items():
                if lesson.get('subject'):
                    day_message += f"🕐 {time}\n"
                    day_message += f"📚 {lesson['subject']}\n"
                    day_message += f"👨‍🏫 {lesson['instructor']}\n"
                    day_message += f"🏢 {lesson['auditorium']}\n"
                    day_message += "─" * 30 + "\n"
                else:
                    day_message += f"🕐 {time} - Аудит.\n"
                    day_message += "─" * 30 + "\n"
            
            if self.last_update:
                day_message += f"\n🔄 Обновлено: {self.last_update.strftime('%d.%m.%Y %H:%M')}"
            
            messages.append(day_message)
        
        return messages
