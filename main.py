import pytz
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
from threading import Thread

from database import create_tables  # Импортируем create_tables из database.py
from checks import *  # Импортируем все проверки
import config  # Импортируем настройки после остальных импортов

def run_checks():
    """
    Функция для запуска всех проверок.
    """
    timezone = pytz.timezone('Europe/Moscow')
    current_time = datetime.now(timezone).strftime('%Y-%m-%d %H:%M:%S')
    print(f"\nЗапуск проверок в {current_time}\n")

    try:
        # Выполнение всех проверок поочередно
        check_overdue_activities()
        check_next_step_missing()
        check_deal_not_moved()
        check_contact_name_missing()
        check_uncontacted_clients()
        check_contact_removal()
        check_additional_phone_number()
        check_missed_calls()
    except Exception as e:
        raise Exception(f"Произошла ошибка во время выполнения проверок: {str(e)}")

def start_scheduler():
    """
    Запускает планировщик, который выполняет проверки по расписанию.
    """
    schedule_hours = config.SCHEDULE_HOURS
    schedule_minute = config.SCHEDULE_MINUTE
    schedule_days = config.SCHEDULE_DAYS

    # Создаем планировщик
    scheduler = BlockingScheduler(timezone='Europe/Moscow')

    # Создаем триггер для запуска в указанные часы
    trigger = CronTrigger(hour=schedule_hours, minute=schedule_minute, day_of_week=schedule_days)

    # Добавляем задачу в планировщик
    scheduler.add_job(run_checks, trigger)

    print("Планировщик проверок запущен.")
    print("Проверки будут выполняться в указанные часы с 8:00 до 18:00 МСК в будние дни.")

    try:
        # Запускаем планировщик
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("Планировщик остановлен.")

def start_flask_app():
    """
    Запускает Flask-приложение.
    """
    from webhooks.webhook import app  # Переносим импорт сюда
    app.run(port=5000)

def main():
    """
    Главная функция, которая запускает сервер и планировщик проверок.
    """
    # Выполняем тестовые проверки
    run_checks()
    
    # Создаем отдельный поток для запуска Flask-приложения
    flask_thread = Thread(target=start_flask_app)
    flask_thread.daemon = True
    flask_thread.start()

    # Запускаем планировщик
    start_scheduler()

if __name__ == "__main__":
    # Создаем таблицы, если они еще не созданы
    create_tables()
    main()
