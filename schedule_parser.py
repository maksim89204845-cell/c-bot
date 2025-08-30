import requests
import PyPDF2
import io
import re
import logging
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
            logging.info("Начинаю скачивание PDF...")
            
            # Преобразуем ссылку для прямого скачивания
            file_id = self.google_drive_url.split('/d/')[1].split('/')[0]
            direct_url = f"https://drive.google.com/uc?export=download&id={file_id}"
            
            logging.info(f"Скачиваю с URL: {direct_url}")
            
            response = requests.get(direct_url, timeout=30)
            response.raise_for_status()
            
            logging.info(f"PDF успешно скачан, размер: {len(response.content)} байт")
            return response.content
            
        except Exception as e:
            logging.error(f"Ошибка скачивания PDF: {e}")
            return None
    
    def extract_text_from_pdf(self, pdf_content: bytes) -> str:
        """Извлекает текст из PDF по страницам и находит страницу с группой 302 Ф"""
        try:
            pdf_file = io.BytesIO(pdf_content)
            reader = PyPDF2.PdfReader(pdf_file)
            
            logging.info(f"PDF содержит {len(reader.pages)} страниц")
            
            # Ищем страницу с группой 302 Ф (с пробелом!)
            target_page = None
            for page_num in range(len(reader.pages)):
                page = reader.pages[page_num]
                page_text = page.extract_text()
                
                logging.info(f"Страница {page_num + 1}: ищу группу 302 Ф...")
                
                if "302 Ф" in page_text:
                    logging.info(f"✅ Группа 302 Ф найдена на странице {page_num + 1}")
                    target_page = page_num
                    break
                else:
                    logging.info(f"❌ Группа 302 Ф НЕ найдена на странице {page_num + 1}")
            
            if target_page is None:
                logging.error("❌ Группа 302 Ф не найдена ни на одной странице!")
                return ""
            
            # Извлекаем текст только с нужной страницы
            page = reader.pages[target_page]
            text = page.extract_text()
            
            logging.info(f"Извлечен текст со страницы {target_page + 1}, длина: {len(text)} символов")
            logging.info(f"Первые 500 символов: {text[:500]}")
            
            return text
            
        except Exception as e:
            logging.error(f"Ошибка при извлечении текста из PDF: {str(e)}")
            return ""
    
    def parse_schedule(self, text: str) -> Dict:
        """Парсит расписание из текста с учетом структуры PDF"""
        schedule = {}
        
        # Отладочная информация
        logging.info(f"=== ОТЛАДКА ПАРСИНГА ===")
        logging.info(f"Длина текста: {len(text)}")
        logging.info(f"Первые 500 символов: {text[:500]}")
        
        # Разбиваем текст на строки
        lines = text.split('\n')
        logging.info(f"Всего строк: {len(lines)}")
        
        current_date = None
        current_main_time = None
        
        # Проходим по строкам
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
                
            logging.info(f"=== Обрабатываю строку {i+1}: '{line}' ===")
            
            # Ищем дату (формат: DD.MM.YYYY)
            date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', line)
            if date_match:
                current_date = date_match.group(1)
                schedule[current_date] = {}
                logging.info(f"✅ Найдена дата: {current_date}")
                continue
            
            # Ищем основное время (формат: HH:MM - HH:MM)
            main_time_match = re.search(r'(\d{2}):(\d{2})\s*-\s*(\d{2}):(\d{2})', line)
            if main_time_match:
                start_hour, start_min, end_hour, end_min = main_time_match.groups()
                current_main_time = f"{start_hour}:{start_min}-{end_hour}:{end_min}"
                logging.info(f"✅ Найдено основное время: {current_main_time}")
                continue
            
            # Ищем время в уроке (формат: HH-MM) - это приоритет!
            lesson_time_match = re.search(r'(\d{2})-(\d{2})', line)
            if lesson_time_match:
                hour, minute = lesson_time_match.groups()
                lesson_time = f"{hour}:{minute}"
                logging.info(f"✅ Найдено время в уроке: {lesson_time}")
                
                # Если нет даты, используем первую найденную или создаем временную
                if not current_date:
                    # Ищем дату в следующих строках или используем первую из расписания
                    for j in range(1, 10):  # Проверяем следующие 10 строк
                        if i + j < len(lines):
                            next_line = lines[i + j].strip()
                            date_in_next = re.search(r'(\d{2}\.\d{2}\.\d{4})', next_line)
                            if date_in_next:
                                current_date = date_in_next.group(1)
                                if current_date not in schedule:
                                    schedule[current_date] = {}
                                logging.info(f"🔍 Найдена дата в следующих строках: {current_date}")
                                break
                    
                    # Если дата все еще не найдена, используем первую доступную
                    if not current_date and schedule:
                        current_date = list(schedule.keys())[0]
                        logging.info(f"🔍 Использую первую доступную дату: {current_date}")
                    elif not current_date:
                        # Создаем временную дату для первого дня
                        current_date = "01.09.2025"  # По умолчанию
                        schedule[current_date] = {}
                        logging.info(f"🔍 Создаю временную дату: {current_date}")
                
                # Теперь у нас есть дата, создаем запись
                if current_date:
                    if lesson_time not in schedule[current_date]:
                        schedule[current_date][lesson_time] = {
                            'subject': '',
                            'instructor': '',
                            'auditorium': ''
                        }
                        logging.info(f"📝 Создана запись для времени {lesson_time}")
                    
                    # Извлекаем предмет (убираем время из начала)
                    subject = line.replace(f"{hour}-{minute}", "").strip()
                    schedule[current_date][lesson_time]['subject'] = subject
                    logging.info(f"📚 Извлечен предмет: '{subject}'")
                    
                    # Следующие строки должны содержать преподавателя и аудиторию
                    # Проверяем следующие 2 строки
                    for j in range(1, 3):
                        if i + j < len(lines):
                            next_line = lines[i + j].strip()
                            logging.info(f"🔍 Проверяю строку {i+j+1}: '{next_line}'")
                            
                            if next_line and not re.search(r'\d{2}:\d{2}', next_line) and not re.search(r'\d{2}\.\d{2}\.\d{4}', next_line):
                                # Это либо преподаватель, либо аудитория
                                if not schedule[current_date][lesson_time]['instructor']:
                                    schedule[current_date][lesson_time]['instructor'] = next_line
                                    logging.info(f"👨‍🏫 Извлечен преподаватель: '{next_line}'")
                                elif not schedule[current_date][lesson_time]['auditorium']:
                                    schedule[current_date][lesson_time]['auditorium'] = next_line
                                    logging.info(f"🏢 Извлечена аудитория: '{next_line}'")
                                    break
                            else:
                                logging.info(f"❌ Строка {i+j+1} не подходит для преподавателя/аудитории")
                        else:
                            logging.info(f"❌ Строка {i+j+1} выходит за пределы")
                
                continue
            
            # Если нет времени в уроке, но есть основное время и дата
            if current_date and current_main_time and '302' in line and not re.search(r'\d{2}-\d{2}', line):
                # Это может быть потоковое занятие без времени в уроке
                logging.info(f"🔄 Найдена строка с 302 без времени: {line}")
                
                # Создаем запись с основным временем
                if current_main_time not in schedule[current_date]:
                    schedule[current_date][current_main_time] = {
                        'subject': '',
                        'instructor': '',
                        'auditorium': ''
                    }
                    logging.info(f"📝 Создана запись для основного времени {current_main_time}")
                
                # Извлекаем предмет
                subject = line.replace('302', '').strip()
                schedule[current_date][current_main_time]['subject'] = subject
                logging.info(f"📚 Извлечен предмет (потоковый): '{subject}'")
                
                # Следующие строки - преподаватель и аудитория
                for j in range(1, 3):
                    if i + j < len(lines):
                        next_line = lines[i + j].strip()
                        logging.info(f"🔍 Проверяю строку {i+j+1} для потокового: '{next_line}'")
                        
                        if next_line and not re.search(r'\d{2}:\d{2}', next_line) and not re.search(r'\d{2}\.\d{2}\.\d{4}', next_line):
                            if not schedule[current_date][current_main_time]['instructor']:
                                schedule[current_date][current_main_time]['instructor'] = next_line
                                logging.info(f"👨‍🏫 Извлечен преподаватель (потоковый): '{next_line}'")
                            elif not schedule[current_date][current_main_time]['auditorium']:
                                schedule[current_date][current_main_time]['auditorium'] = next_line
                                logging.info(f"🏢 Извлечена аудитория (потоковый): '{next_line}'")
                                break
                        else:
                            logging.info(f"❌ Строка {i+j+1} не подходит для потокового")
                    else:
                        logging.info(f"❌ Строка {i+j+1} выходит за пределы для потокового")
        
        logging.info(f"📊 Итоговое расписание: {schedule}")
        logging.info(f"=== КОНЕЦ ОТЛАДКИ ===")
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
            logging.error(f"Ошибка обновления расписания: {e}")
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
