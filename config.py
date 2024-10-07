import os
from dotenv import load_dotenv

load_dotenv()


# Настройки
WEBHOOK_URL = os.getenv('BITRIX24_WEBHOOK_URL')
APPLICATION_TOKEN = os.getenv('APPLICATION_TOKEN')

SHEET_NAME = os.getenv('SHEET_NAME')
WORKSHEET_NAME = os.getenv('WORKSHEET_NAME')
CREDENTIALS_FILE = os.getenv('CREDENTIALS_FILE')

SCHEDULE_HOURS = os.getenv('SCHEDULE_HOURS', '8,10,12,14,16,18')
SCHEDULE_MINUTE = int(os.getenv('SCHEDULE_MINUTE', '0'))
SCHEDULE_DAYS = os.getenv('SCHEDULE_DAYS', 'mon-fri') 

DATABASE = {
    'NAME': os.getenv('DATABASE_NAME'),
    'USER': os.getenv('DATABASE_USER'),
    'PASSWORD': os.getenv('DATABASE_PASSWORD'),
    'HOST': os.getenv('DATABASE_HOST'),
    'PORT': os.getenv('DATABASE_PORT')
}