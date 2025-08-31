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
            if '/d/' not in self.google_drive_url:
                logging.error("❌ Неверный формат Google Drive URL")
                return None
                
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
        """Парсит расписание из текста с учетом структуры потоковых занятий"""
        schedule = {}
        
        # Отладочная информация
        logging.info(f"=== ОТЛАДКА ПАРСИНГА ===")
        logging.info(f"Длина текста: {len(text)}")
        logging.info(f"Первые 500 символов: {text[:500]}")
        
        # Разбиваем текст на строки
        lines = text.split('\n')
        logging.info(f"Всего строк: {len(lines)}")
        
        current_date = None
        temp_lessons = {}  # Временные уроки до нахождения даты
        
        # Проходим по строкам
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
                
            logging.info(f"=== Обрабатываю строку {i+1}: '{line}' ===")
            
            # Ищем дату (формат: DD.MM.YYYY)
            date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', line)
            if date_match:
                new_date = date_match.group(1)
                
                # Если у нас есть временные уроки, переносим их на новую дату
                if temp_lessons:
                    logging.info(f"🔄 Переношу {len(temp_lessons)} временных уроков на {new_date}")
                    if new_date not in schedule:
                        schedule[new_date] = {}
                    schedule[new_date].update(temp_lessons)
                    temp_lessons.clear()
                
                current_date = new_date
                if current_date not in schedule:
                    schedule[current_date] = {}
                logging.info(f"✅ Найдена дата: {current_date}")
                continue
            
            # Ищем время в уроке (формат: HH-MM) - это приоритет!
            lesson_time_match = re.search(r'(\d{2})-(\d{2})', line)
            if lesson_time_match:
                hour, minute = lesson_time_match.groups()
                lesson_time = f"{hour}:{minute}"
                logging.info(f"✅ Найдено время в уроке: {lesson_time}")
                
                # Извлекаем предметы для группы 302 Ф из правой колонки
                subjects = self._extract_subjects_for_302f(line)
                
                # Ищем преподавателей и аудитории в следующих строках
                instructor_auditorium = self._extract_instructor_auditorium(lines, i+1)
                
                lesson_data = {
                    'subject': subjects,
                    'instructor': instructor_auditorium.get('instructor', ''),
                    'auditorium': instructor_auditorium.get('auditorium', '')
                }
                
                # Проверяем, что предмет не пустой
                if subjects and subjects.strip():
                    if current_date and current_date in schedule:
                        if lesson_time not in schedule[current_date]:
                            schedule[current_date][lesson_time] = lesson_data
                            logging.info(f"📝 Создана запись для времени {lesson_time} в дате {current_date}")
                        else:
                            logging.info(f"⚠️ Время {lesson_time} уже существует в дате {current_date}")
                    else:
                        # Сохраняем во временные уроки
                        temp_lessons[lesson_time] = lesson_data
                        logging.info(f"📝 Сохранен временный урок для времени {lesson_time}")
                else:
                    logging.info(f"⚠️ Предмет пустой для времени {lesson_time}, пропускаю")
                
                continue
            
            # Ищем основное время (формат: HH:MM - HH:MM)
            main_time_match = re.search(r'(\d{2}):(\d{2})\s*-\s*(\d{2}):(\d{2})', line)
            if main_time_match:
                start_hour, start_min, end_hour, end_min = main_time_match.groups()
                current_main_time = f"{start_hour}:{start_min}-{end_hour}:{end_min}"
                logging.info(f"✅ Найдено основное время: {current_main_time}")
                continue
        
        # В конце переносим оставшиеся временные уроки на первую дату
        if temp_lessons and schedule:
            first_date = list(schedule.keys())[0]
            logging.info(f"🔄 Переношу {len(temp_lessons)} оставшихся временных уроков на {first_date}")
            if first_date not in schedule:
                schedule[first_date] = {}
            schedule[first_date].update(temp_lessons)
        elif temp_lessons and not schedule:
            # Если нет дат вообще, создаем временную дату
            temp_date = "01.09.2025"
            schedule[temp_date] = temp_lessons
            logging.info(f"🔄 Создаю временную дату {temp_date} для {len(temp_lessons)} уроков")
        
        # Сортируем уроки по времени для каждого дня
        for date in schedule:
            schedule[date] = dict(sorted(schedule[date].items(), key=lambda x: x[0]))
            logging.info(f"📅 Сортировка для {date}: {list(schedule[date].keys())}")
        
        # Проверяем, что расписание не пустое
        total_lessons = sum(len(day_schedule) for day_schedule in schedule.values())
        logging.info(f"📊 Всего найдено уроков: {total_lessons}")
        
        logging.info(f"📊 Итоговое расписание: {schedule}")
        logging.info(f"=== КОНЕЦ ОТЛАДКИ ===")
        return schedule
    
    def _extract_subjects_for_302f(self, line: str) -> str:
        """Извлекает предметы для группы 302 Ф из строки"""
        # Убираем время из начала строки
        line = re.sub(r'^\d{2}-\d{2}\s*', '', line)
        
        # Ищем предметы для группы 302 Ф (правая колонка)
        if '302 Ф' in line:
            # Берем правую часть после "302 Ф"
            parts = line.split('302 Ф')
            if len(parts) > 1:
                subject_part = parts[1].strip()
                # Убираем аудитории (начинающиеся с цифр)
                subject_part = re.sub(r'\d+\s+(?:Советская|Полесская|Ломоносова)', '', subject_part)
                subject_part = re.sub(r'Спортивный зал', '', subject_part)
                subject_part = re.sub(r'\s+', ' ', subject_part).strip()
                logging.info(f"📚 Извлечен предмет для 302 Ф: '{subject_part}'")
                return subject_part
        
        # Если "302 Ф" не найден, но есть "301 Ф", берем правую часть
        if '301 Ф' in line:
            parts = line.split('301 Ф')
            if len(parts) > 1:
                # Берем правую часть и ищем предметы для 302 Ф
                right_part = parts[1].strip()
                # Убираем аудитории
                right_part = re.sub(r'\d+\s+(?:Советская|Полесская|Ломоносова)', '', right_part)
                right_part = re.sub(r'Спортивный зал', '', right_part)
                # Убираем лишний текст с временем
                right_part = re.sub(r'\d{2}-\d{2}', '', right_part)
                right_part = re.sub(r'\d{2}:\d{2}\s*-\s*\d{2}:\d{2}', '', right_part)
                right_part = re.sub(r'\s+', ' ', right_part).strip()
                logging.info(f"📚 Извлечен предмет из правой части: '{right_part}'")
                return right_part
        
        # Если ничего не найдено, берем всю строку и убираем аудитории
        line = re.sub(r'\d+\s+(?:Советская|Полесская|Ломоносова)', '', line)
        line = re.sub(r'Спортивный зал', '', line)
        # Убираем лишний текст с временем
        line = re.sub(r'\d{2}-\d{2}', '', line)
        line = re.sub(r'\d{2}:\d{2}\s*-\s*\d{2}:\d{2}', '', line)
        line = re.sub(r'\s+', ' ', line).strip()
        
        logging.info(f"📚 Извлечен предмет: '{line}'")
        return line
    
    def _extract_instructor_auditorium(self, lines: List[str], start_line: int) -> Dict:
        """Извлекает преподавателя и аудиторию из следующих строк"""
        result = {'instructor': '', 'auditorium': ''}
        
        # Проверяем следующие 2 строки
        for i in range(start_line, min(start_line + 2, len(lines))):
            line = lines[i].strip()
            if not line:
                continue
                
            logging.info(f"🔍 Проверяю строку {i+1}: '{line}'")
            
            # Поиск преподавателя (ФИО в формате "Фамилия И.О.")
            instructor_match = re.search(r'([А-Я][а-я]+\s+[А-Я]\.[А-Я]\.)', line)
            if instructor_match and not result['instructor']:
                result['instructor'] = instructor_match.group(1)
                logging.info(f"👨‍🏫 Извлечен преподаватель: '{result['instructor']}'")
                continue
            
            # Поиск аудитории
            auditorium_match = re.search(r'(?:Аудит\.\s*)?(\d+\s+(?:Советская|Полесская|Ломоносова)|Спортивный зал)', line)
            if auditorium_match and not result['auditorium']:
                result['auditorium'] = auditorium_match.group(1)
                logging.info(f"🏢 Извлечена аудитория: '{result['auditorium']}'")
                continue
            
            # Если строка не подходит для преподавателя/аудитории
            if not instructor_match and not auditorium_match:
                logging.info(f"❌ Строка {i+1} не подходит для преподавателя/аудитории")
        
        return result
    
    def _find_date_in_next_lines(self, lines: List[str], start_line: int, max_lines: int) -> Optional[str]:
        """Ищет дату в следующих строках"""
        for i in range(start_line, min(start_line + max_lines, len(lines))):
            line = lines[i].strip()
            date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', line)
            if date_match:
                found_date = date_match.group(1)
                logging.info(f"🔍 Найдена дата в следующих строках: {found_date}")
                return found_date
        return None
    
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
            logging.info("🔄 Начинаю обновление расписания...")
            pdf_content = self.download_pdf()
            if pdf_content:
                text = self.extract_text_from_pdf(pdf_content)
                if text:
                    self.schedule_data = self.parse_schedule(text)
                    self.last_update = datetime.now()
                    
                    # Проверяем, что расписание не пустое
                    total_lessons = sum(len(day_schedule) for day_schedule in self.schedule_data.values())
                    logging.info(f"✅ Расписание обновлено! Всего уроков: {total_lessons}")
                    return True
                else:
                    logging.error("❌ Не удалось извлечь текст из PDF")
                    return False
            else:
                logging.error("❌ Не удалось скачать PDF")
                return False
        except Exception as e:
            logging.error(f"❌ Ошибка обновления расписания: {e}")
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
                    if lesson.get('instructor'):
                        message += f"👨‍🏫 {lesson['instructor']}\n"
                    if lesson.get('auditorium'):
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
                        message += f"🕐 {time} - {lesson['subject']}"
                        if lesson.get('instructor'):
                            message += f" ({lesson['instructor']}"
                            if lesson.get('auditorium'):
                                message += f", {lesson['auditorium']}"
                            message += ")"
                        message += "\n"
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
        
        # Сортируем даты для правильного порядка
        sorted_dates = sorted(schedule.keys(), key=lambda x: datetime.strptime(x, '%d.%m.%Y'))
        
        for date in sorted_dates:
            day_schedule = schedule[date]
            
            if not day_schedule:  # Пропускаем пустые дни
                continue
                
            day_message = f"📅 Расписание на {date}:\n\n"
            
            # Сортируем уроки по времени
            sorted_times = sorted(day_schedule.keys(), key=lambda x: x)
            
            for time in sorted_times:
                lesson = day_schedule[time]
                if lesson.get('subject'):
                    day_message += f"🕐 {time}\n"
                    day_message += f"📚 {lesson['subject']}\n"
                    if lesson.get('instructor'):
                        day_message += f"👨‍🏫 {lesson['instructor']}\n"
                    if lesson.get('auditorium'):
                        day_message += f"🏢 {lesson['auditorium']}\n"
                    day_message += "─" * 30 + "\n"
                else:
                    day_message += f"🕐 {time} - Аудит.\n"
                    day_message += "─" * 30 + "\n"
            
            if self.last_update:
                day_message += f"\n🔄 Обновлено: {self.last_update.strftime('%d.%m.%Y %H:%M')}"
            
            messages.append(day_message)
        
        # Если нет сообщений, возвращаем одно сообщение
        if not messages:
            return ["📅 Расписание на неделю не найдено или все дни пустые."]
        
        return messages
