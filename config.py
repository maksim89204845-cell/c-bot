# Конфигурация бота
import os

# Токен бота
BOT_TOKEN = os.getenv('BOT_TOKEN', '8380069376:AAEB7UesvgxymReqmnQTIvIMNABB5_6N_gc')

# URL расписания на Google Drive
GOOGLE_DRIVE_URL = "https://drive.google.com/file/d/152JZ6IMxa07Z1oIjzv7NLhm1LhQUynzP/view?usp=sharing"

# Настройки группы
DEFAULT_GROUP = "302Ф"

# Настройки обновления
UPDATE_INTERVAL_HOURS = 1  # Обновлять расписание каждый час

# Настройки логирования
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Настройки сообщений
MAX_MESSAGE_LENGTH = 4096  # Максимальная длина сообщения в Telegram
