from datetime import datetime
import pytz
from bitrix24_api import call_api
from utils import *
from sqlalchemy.orm import Session
from database import get_db


TIMEZONE = pytz.timezone('Europe/Moscow')

def check_missed_calls():
    """
    Проверяет, есть ли успешные звонки (более 20 секунд) после fixed_time.
    Если успешного звонка нет, проверяет количество неуспешных звонков в зависимости от времени fixed_time.
    Если условия не выполнены, выводит информацию о сделке и ответственном и записывает данные в Google Sheets.
    """
    print('[Проверка 8]')
    rows_to_add = []  # Для записи данных в Google Sheets

    # Текущее время в часовом поясе Москвы
    current_time = datetime.now(TIMEZONE)

    # Создаем сессию базы данных
    db = next(get_db())

    try:
        # Получаем все deal_id и fixed_time из diff_assigment_id
        deals = db.query(DiffAssignmentID.deal_id, DiffAssignmentID.fixed_time).all()

        # Проверяем каждую сделку
        for deal in deals:
            deal_id = deal.deal_id
            fixed_time_str = deal.fixed_time
            fixed_time = datetime.fromisoformat(fixed_time_str).astimezone(TIMEZONE)
            assigned_by_id = None

            # Получаем звонки, связанные со сделкой
            activity_params = {
                "filter": {
                    "OWNER_ID": deal_id,
                    "OWNER_TYPE_ID": 2,  # Тип ID для сделки в Bitrix24
                    "TYPE_ID": 2,  # Тип активности (2 = звонок в Bitrix24)
                    ">=START_TIME": fixed_time_str
                },
                "order": {
                    "START_TIME": "ASC"
                },
                "select": ["ID", "START_TIME", "END_TIME"]
            }

            activities_response = call_api('crm.activity.list', activity_params, 'POST')
            
            if activities_response and 'result' in activities_response:
                calls = activities_response['result']

                if not calls:  # Если нет звонков
                    continue

                successful_call = False
                unsuccessful_calls = []

                for call in calls:
                    start_time = datetime.strptime(call['START_TIME'], '%Y-%m-%dT%H:%M:%S%z')
                    end_time = datetime.strptime(call['END_TIME'], '%Y-%m-%dT%H:%M:%S%z')

                    # Вычисляем длительность звонка в секундах
                    call_duration_seconds = (end_time - start_time).total_seconds()

                    # Проверяем успешность звонка (больше 20 секунд)
                    if call_duration_seconds > 20:
                        successful_call = True
                        break
                    else:
                        unsuccessful_calls.append(call)

                # Если успешного звонка нет
                if not successful_call:
                    # Определяем, сколько нужно неуспешных звонков
                    required_unsuccessful_calls = 3
                    if fixed_time.hour >= 13 and fixed_time.hour < 16:
                        required_unsuccessful_calls = 2
                    elif fixed_time.hour >= 16 and fixed_time.hour < 19:
                        required_unsuccessful_calls = 1

                    # Проверяем количество неуспешных звонков
                    if len(unsuccessful_calls) < required_unsuccessful_calls:
                        # Если не хватает неуспешных звонков, выводим информацию о сделке
                        deal_response = call_api('crm.deal.get', {"id": deal_id}, 'POST')
                        if deal_response and 'result' in deal_response:
                            deal_info = deal_response['result']
                            assigned_by_id = deal_info.get('ASSIGNED_BY_ID')

                            # Получаем имя ответственного
                            user_name = get_user_names([assigned_by_id]).get(assigned_by_id, f"ID {assigned_by_id}")
                            
                            # Формируем замечание для Google Sheets
                            remark = "Недостаточно неуспешных звонков после фиксированного времени"
                            
                            # Формируем строку для записи в Google Sheets
                            row = [
                                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),  # Текущая дата и время
                                "Program",
                                deal_id,
                                "",
                                "",
                                user_name,
                                remark
                            ]
                            rows_to_add.append(row)

                            # Вывод только важной информации о сделке
                            important_info = {
                                'ID': deal_info.get('ID'),
                                'Название': deal_info.get('TITLE'),
                                'Контакт': deal_info.get('CONTACT_ID'),
                                'Ответственный': user_name,
                                'Статус': deal_info.get('STAGE_ID')
                            }
                            print(f"Информация о сделке: {important_info}")
                    else:
                        print(f"Сделка ID {deal_id} имеет достаточное количество неуспешных звонков: {len(unsuccessful_calls)}")
                        print("Успешная проверка")
                else:
                    print(f"Сделка ID {deal_id} имеет успешный звонок.")
                    print("Успешная проверка")
            else:
                print(f"Не удалось получить данные о звонках для сделки ID {deal_id}.")

        # Если есть строки для добавления в Google Sheets
        if rows_to_add:
            write_to_sheet(rows_to_add)

        print("Успешная проверка")

    finally:
        db.close()
