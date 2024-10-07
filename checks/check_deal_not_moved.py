from datetime import datetime, timedelta
import pytz
from bitrix24_api import call_api
from utils import *

def get_deals_in_general_pipeline():
    """
    Функция для получения всех активных сделок в воронке 'Общая' (CATEGORY_ID = 0).
    """
    DEALS_METHOD = 'crm.deal.list'

    # Параметры запроса
    params = {
        'filter': {
            'CATEGORY_ID': 0,  # 'Общая' воронка, убедитесь, что CATEGORY_ID соответствует вашей системе
            'CLOSED': 'N'      # Только незакрытые сделки
        },
        'select': ['ID', 'TITLE', 'STAGE_ID', 'DATE_CREATE', 'DATE_MODIFY', 'ASSIGNED_BY_ID']
    }

    all_deals = []
    start = 0

    while True:
        params['start'] = start
        data = call_api(DEALS_METHOD, params=params, http_method='POST')

        if data and 'result' in data:
            deals = data['result']
            all_deals.extend(deals)

            if 'next' in data:
                start = data['next']
            else:
                break
        else:
            print("Ошибка при получении списка сделок.")
            break

    return all_deals


def get_last_stage_change_time(deal_id):
    """
    Функция для получения даты последнего изменения стадии сделки.
    """
    STAGE_HISTORY_METHOD = 'crm.stagehistory.list'

    params = {
        'entityTypeId': 2,  # Тип сущности: 2 - сделка
        'filter': {
            'OWNER_ID': deal_id
        },
        'order': {
            'ID': 'DESC'
        },
        'select': ['ID', 'STAGE_ID', 'CREATED_TIME']
    }

    data = call_api(STAGE_HISTORY_METHOD, params=params, http_method='POST')

    if data and 'result' in data and 'items' in data['result'] and data['result']['items']:
        # Результаты отсортированы по ID DESC, первый элемент - последний переход
        last_stage_change = data['result']['items'][0]
        last_stage_change_time_str = last_stage_change['CREATED_TIME']
        try:
            last_stage_change_time = datetime.strptime(last_stage_change_time_str, '%Y-%m-%dT%H:%M:%S%z')
            return last_stage_change_time
        except ValueError:
            print(f"Неверный формат даты для сделки ID {deal_id}: {last_stage_change_time_str}")
            return None
    else:
        # Если нет истории изменений стадии, возможно, сделка еще на начальной стадии
        return None


def get_last_activity_time(deal_id):
    """
    Функция для получения даты последнего действия по сделке.
    """
    ACTIVITIES_METHOD = 'crm.activity.list'

    params = {
        'filter': {
            'OWNER_ID': deal_id,
            'OWNER_TYPE_ID': 2,  # 2 соответствует DEAL
            'TYPE_ID': 6,        # 6 соответствует TASK
            'COMPLETED': 'Y'     # Фильтр по завершенным действиям
        },
        'order': {
            'END_TIME': 'DESC'  # Используем END_TIME для сортировки по времени завершения
        },
        'select': ['ID', 'LAST_UPDATED', 'END_TIME']
    }

    data = call_api(ACTIVITIES_METHOD, params=params, http_method='POST')

    if data and 'result' in data and data['result']:
        # Первый элемент - последняя активность
        last_activity = data['result'][0]
        last_activity_time_str = last_activity.get('LAST_UPDATED') or last_activity.get('END_TIME')

        try:
            last_activity_time = datetime.strptime(last_activity_time_str, '%Y-%m-%dT%H:%M:%S%z')
            return last_activity_time
        except ValueError:
            print(f"Неверный формат даты для активности по сделке ID {deal_id}: {last_activity_time_str}")
            return None
    else:
        # Если нет активностей, возможно, активности не было
        return None


def check_deal_not_moved():
    """
    Проверка сделок, которые не были переведены по воронке в течение 6 часов после совершенного действия.
    """
    deals = get_deals_in_general_pipeline()
    print(f"[Проверка 3] Активных сделок в 'Общей' воронке: {len(deals)}")

    deals_not_moved = []
    rows_to_add = []  # Для записи данных в Google Sheets

    timezone = pytz.timezone('Europe/Moscow')
    now = datetime.now(timezone)

    for deal in deals:
        deal_id = deal['ID']
        deal_title = deal['TITLE']
        assigned_by_id = deal['ASSIGNED_BY_ID']

        # Получаем дату последнего изменения стадии
        last_stage_change_time = get_last_stage_change_time(deal_id)

        if last_stage_change_time is None:
            # Если нет данных об изменении стадии, используем дату создания сделки
            last_stage_change_time = datetime.strptime(deal['DATE_CREATE'], '%Y-%m-%dT%H:%M:%S%z')

        # Получаем дату последней активности по сделке
        last_activity_time = get_last_activity_time(deal_id)

        if last_activity_time is None:
            # Если нет активности, используем дату создания сделки
            last_activity_time = datetime.strptime(deal['DATE_CREATE'], '%Y-%m-%dT%H:%M:%S%z')

        # Проверяем, прошло ли более 6 часов с момента последнего действия
        time_since_last_activity = now - last_activity_time.astimezone(timezone)

        if time_since_last_activity > timedelta(hours=6):
            # Проверяем, было ли изменение стадии после последнего действия
            if last_stage_change_time < last_activity_time:
                # Стадия не менялась после последнего действия
                deals_not_moved.append({
                    'deal_id': deal_id,
                    'deal_title': deal_title,
                    'assigned_by_id': assigned_by_id,
                    'last_activity_time': last_activity_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'last_stage_change_time': last_stage_change_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'hours_since_last_activity': time_since_last_activity.total_seconds() / 3600
                })

    print(f"Сделок, не переведенных по воронке в течение 6 часов после последнего действия: {len(deals_not_moved)}")

    if deals_not_moved:
        # Получаем имена ответственных
        user_ids = [item['assigned_by_id'] for item in deals_not_moved]
        user_names = get_user_names(user_ids)

        # Выводим информацию и добавляем строки для записи в Google Sheets
        print("\nСписок таких сделок:")
        for item in deals_not_moved:
            assigned_name = user_names.get(item['assigned_by_id'], f"ID {item['assigned_by_id']}")
            remark = f"Сделка не была переведена по воронке в течение 6 часов после последнего действия"
            
            # Печатаем в терминал
            print(f"Сделка ID: {item['deal_id']}, Название: {item['deal_title']}, Ответственный: {assigned_name}, Последнее действие: {item['last_activity_time']}, Последнее изменение стадии: {item['last_stage_change_time']}, Часов с момента последнего действия: {item['hours_since_last_activity']:.2f}")
            
            # Формируем строку для записи в Google Sheets
            row = [
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),  # Текущая дата и время
                "Program",
                item['deal_id'],
                "",
                "",
                assigned_name,
                remark
            ]
            rows_to_add.append(row)
    else:
        print("Все сделки были переведены по воронке в течение 6 часов после последнего действия.")

    # Если есть строки для добавления в Google Sheets
    if rows_to_add:
        write_to_sheet(rows_to_add)

    # Возвращаем список для дальнейшей обработки, если потребуется
    return deals_not_moved
