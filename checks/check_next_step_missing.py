from datetime import datetime, timedelta
import pytz
from bitrix24_api import call_api
from utils import *

def get_completed_activities():
    """
    Функция для получения завершенных дел (активностей) за последние 6 часов, где LAST_UPDATED не раньше чем 2 часа назад.
    """
    ACTIVITIES_METHOD = 'crm.activity.list'

    # Текущее время и фильтры по времени
    timezone = pytz.timezone('Europe/Moscow')
    now = datetime.now(timezone)
    six_hours_ago = now - timedelta(hours=6)
    two_hours_ago = now - timedelta(hours=2)

    # Форматируем даты в строки в формате ISO 8601
    six_hours_ago_str = six_hours_ago.strftime('%Y-%m-%dT%H:%M:%S%z')
    two_hours_ago_str = two_hours_ago.strftime('%Y-%m-%dT%H:%M:%S%z')

    # Параметры запроса: завершенные дела за последние 6 часов с фильтром по LAST_UPDATED
    params = {
        'filter': {
            'COMPLETED': 'Y',      # Завершенные дела
            '>=LAST_UPDATED': six_hours_ago_str,  # Обновленные не раньше чем 6 часов назад
            '<=LAST_UPDATED': two_hours_ago_str,  # Обновленные не позже чем 2 часа назад
            'OWNER_TYPE_ID': 2,    # Сделка
            'TYPE_ID': 6,          # Соответствует задаче (TASK)
        },
        'select': ['ID', 'SUBJECT', 'RESPONSIBLE_ID', 'OWNER_ID', 'OWNER_TYPE_ID', 'END_TIME', 'LAST_UPDATED']
    }

    all_activities = []
    start = 0

    while True:
        params['start'] = start
        data = call_api(ACTIVITIES_METHOD, params=params, http_method='POST')
        if data and 'result' in data and data['result']:
            activities = data['result']
            all_activities.extend(activities)

            if 'next' in data:
                start = data['next']
            else:
                break
        else:
            print("Ошибка при получении завершенных дел.")
            break

    return all_activities


def check_next_step_missing():
    """
    Функция проверяет ответственных за сделки завершенные за последние 6 часов,
    и сравнивает с теми, кто создал новые сделки за последние 2 часа.
    """
    # Получаем завершенные дела за последние 6 часов
    completed_activities = get_completed_activities()
    print(f"[Проверка 2] Завершенных дел за последние 6 часов: {len(completed_activities)}")

    missing_next_steps = []
    rows_to_add = []  # Для записи данных в Google Sheets

    # Извлекаем ответственных (responsible_id) из завершенных сделок
    responsible_ids_from_completed = {activity['RESPONSIBLE_ID'] for activity in completed_activities}

    # Получаем текущие время и время 2 часа назад
    timezone = pytz.timezone('Europe/Moscow')
    now = datetime.now(timezone)
    two_hours_ago = now - timedelta(hours=2)
    two_hours_ago_str = two_hours_ago.strftime('%Y-%m-%dT%H:%M:%S%z')

    # Параметры запроса для получения новых сделок, созданных за последние 2 часа
    params = {
        'filter': {
            '>=DATE_CREATE': two_hours_ago_str,  # Новые сделки, созданные за последние 2 часа
            'OWNER_TYPE_ID': 2,  # Сделка
        },
        'select': ['ID', 'TITLE', 'ASSIGNED_BY_ID', 'DATE_CREATE']
    }

    new_deals = []
    start = 0

    while True:
        params['start'] = start
        data = call_api('crm.deal.list', params=params, http_method='POST')
        if data and 'result' in data and data['result']:
            deals = data['result']
            new_deals.extend(deals)

            if 'next' in data:
                start = data['next']
            else:
                break
        else:
            print("Ошибка при получении новых сделок.")
            break

    print(f"[Проверка] Новых сделок за последние 2 часа: {len(new_deals)}")

    # Извлекаем ответственных (assigned_by_id) из новых сделок
    responsible_ids_from_new_deals = {deal['ASSIGNED_BY_ID'] for deal in new_deals}

    # Проверяем, кто из ответственных из завершенных дел не создал новые сделки
    for responsible_id in responsible_ids_from_completed:
        if responsible_id not in responsible_ids_from_new_deals:
            # Если ответственный не создал новых сделок, добавляем его в список
            missing_next_steps.append({
                'responsible_id': responsible_id,
                'remark': f"Ответственный ID {responsible_id} не создал новую сделку за последние 2 часа."
            })

    print(f"Ответственных без новых сделок за последние 2 часа: {len(missing_next_steps)}")

    if missing_next_steps:
        # Получаем имена ответственных
        user_ids = [item['responsible_id'] for item in missing_next_steps]
        user_names = get_user_names(user_ids)

        # Выводим информацию и добавляем строки для Google Sheets
        print("\nОтветственные без новых сделок за последние 2 часа:")
        for item in missing_next_steps:
            responsible_name = user_names.get(item['responsible_id'], f"ID {item['responsible_id']}")
            remark = item['remark']

            # Печатаем в терминал
            print(f"Ответственный: {responsible_name} ({item['responsible_id']})")

            # Формируем строку для записи в Google Sheets
            row = [
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),  # Текущая дата и время
                "Program",
                "",
                "",
                "",
                responsible_name,
                remark
            ]
            rows_to_add.append(row)
    else:
        print("Все ответственные создали новые сделки за последние 2 часа.")

    # Если есть строки для добавления в Google Sheets
    if rows_to_add:
        write_to_sheet(rows_to_add)

    # Возвращаем список ответственных без новых сделок для дальнейшей обработки, если потребуется
    return missing_next_steps
