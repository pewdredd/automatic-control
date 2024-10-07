from datetime import datetime, timedelta
import pytz
from bitrix24_api import call_api
from utils import *
from sqlalchemy.orm import Session
from database import get_db

TIMEZONE = pytz.timezone('Europe/Moscow')

def get_unchecked_deals():
    """
    Возвращает сделки из актуальной таблицы, у которых checked=False.
    """
    db = next(get_db())  # Создаем сессию базы данных
    try:
        # Запрос к таблице diff_assigment_id для получения сделок с checked=False
        results = db.query(DiffAssignmentID.deal_id, DiffAssignmentID.fixed_time).filter(DiffAssignmentID.checked == False).all()
        return [(result.deal_id, result.fixed_time) for result in results]
    finally:
        db.close()

def get_deal_activities(deal_id, fixed_time):
    """
    Получает историю активности сделки с момента зафиксированного времени.
    """
    method = 'crm.activity.list'
    params = {
        'filter': {
            'OWNER_ID': deal_id,
            'OWNER_TYPE_ID': 2,  # Тип владельца: 2 означает сделку в Bitrix24
            'TYPE_ID': 2,        # Тип активности: 2 означает звонок
            'COMPLETED': 'Y',    # Ищем только завершенные активности
            '>=END_TIME': fixed_time  # Начинаем поиск с зафиксированного времени
        },
        'order': {
            'END_TIME': 'ASC'
        }
    }

    response = call_api(method, params=params, http_method='POST')
    
    # Проверка и возврат результата
    if response and 'result' in response:
        return response['result']
    return []

def check_uncontacted_clients():
    """
    Проверка незаконтакченных клиентов по сделкам.
    """
    print(f"[Проверка 5]")

    unchecked_deals = get_unchecked_deals()
    deals_to_notify = []
    rows_to_add = []  # Для записи данных в Google Sheets
    current_time = datetime.now(TIMEZONE)
    
    deal_ids = []
    deals_data = {}

    for deal_id, fixed_time in unchecked_deals:
        deal_ids.append(deal_id)

    # Получаем данные о сделках одним запросом
    if deal_ids:
        deals_data_list = get_deal_data(deal_ids)
        deals_data = {deal['ID']: deal for deal in deals_data_list}

    for deal_id, fixed_time in unchecked_deals:
        # Исправляем форматирование даты и времени для учета микросекунд
        fixed_time_dt = datetime.strptime(fixed_time, '%Y-%m-%dT%H:%M:%S.%f%z')

        # Проверка, передан ли клиент после 18:00
        if fixed_time_dt.hour >= 18:
            next_day_9am = fixed_time_dt.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
            time_limit = next_day_9am
        else:
            time_limit = fixed_time_dt + timedelta(hours=1)

        # Получаем историю активности сделки
        activities = get_deal_activities(deal_id, fixed_time)

        call_found_within_limit = False

        for activity in activities:
            end_time_str = activity.get('END_TIME')
            end_time = datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M:%S%z')

            # Проверяем, был ли звонок в течение заданного периода
            if fixed_time_dt < end_time <= time_limit:
                call_found_within_limit = True
                break

        # Если звонок не был найден в течение заданного периода
        if not call_found_within_limit:
            deal_data = deals_data.get(str(deal_id), {})
            responsible_id = deal_data.get('ASSIGNED_BY_ID')
            created_by_id = deal_data.get('CREATED_BY_ID')

            deals_to_notify.append({
                'deal_id': deal_id,
                'responsible_id': responsible_id,
                'created_by_id': created_by_id,
                'fixed_time': fixed_time,
                'call_status': f"Не найден звонок в течение заданного периода ({'до 09:00' if fixed_time_dt.hour >= 18 else 'в течение часа'})"
            })

    print(f"Сделок, требующих внимания: {len(deals_to_notify)}")

    if deals_to_notify:
        user_ids = set()
        for item in deals_to_notify:
            if item['responsible_id']:
                user_ids.add(item['responsible_id'])
            if item['created_by_id']:
                user_ids.add(item['created_by_id'])

        user_names = get_user_names(list(user_ids))

        # Выводим подробную информацию о сделках
        print("\nСписок сделок для уведомления:")
        for item in deals_to_notify:
            responsible_name = user_names.get(item['responsible_id'], f"ID {item['responsible_id']}")
            created_by_name = user_names.get(item['created_by_id'], f"ID {item['created_by_id']}")

            print(
                f"Сделка ID: {item['deal_id']}, "
                f"Зафиксированное время: {item['fixed_time']}, "
                f"Статус звонка: {item['call_status']}, "
                f"Ответственный: {responsible_name} (ID {item['responsible_id']}), "
                f"Создатель сделки: {created_by_name} (ID {item['created_by_id']})"
            )

            # Формируем замечание для Google Sheets
            remark = item['call_status']
            
            # Формируем строку для записи в Google Sheets
            row = [
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),  # Текущая дата и время
                "Program",
                item['deal_id'],
                "",
                "",
                responsible_name,
                remark
            ]
            rows_to_add.append(row)

    else:
        print("Нет сделок, требующих внимания.")

    # Если есть строки для добавления в Google Sheets
    if rows_to_add:
        write_to_sheet(rows_to_add)
