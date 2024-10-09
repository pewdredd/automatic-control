from datetime import datetime, timedelta
import pytz
from bitrix24_api import call_api
from utils import *

def get_deals_with_recent_activities():
    """
    Функция для получения сделок, в которых последнее действие завершено не раньше 3 дней назад и не позже 6 часов назад.
    """
    ACTIVITIES_METHOD = 'crm.activity.list'

    # Текущее время и фильтры по времени
    timezone = pytz.timezone('Europe/Moscow')
    now = datetime.now(timezone)
    three_days_ago = now - timedelta(days=3)
    six_hours_ago = now - timedelta(hours=6)

    # Форматируем даты в строки в формате ISO 8601
    three_days_ago_str = three_days_ago.strftime('%Y-%m-%dT%H:%M:%S%z')
    six_hours_ago_str = six_hours_ago.strftime('%Y-%m-%dT%H:%M:%S%z')

    # Параметры запроса для завершенных активностей (дел) за последние 3 дня и до 6 часов назад
    params = {
        'filter': {
            'COMPLETED': 'Y',      # Завершенные дела
            '>=END_TIME': three_days_ago_str,  # Не раньше чем 3 дня назад
            '<=END_TIME': six_hours_ago_str,   # Не позже чем 6 часов назад
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
            print("Ошибка при получении завершенных активностей.")
            break

    return all_activities


def get_stage_changes_for_deals(deal_ids):
    """
    Получает историю изменений стадии для всех сделок из списка deal_ids.
    """
    STAGE_HISTORY_METHOD = 'crm.stagehistory.list'

    # Преобразуем множество в список
    deal_ids_list = list(deal_ids)

    params = {
        'entityTypeId': 2,  # Тип сущности: 2 - сделка
        'filter': {
            'OWNER_ID': deal_ids_list  # Передаем список сделок с помощью оператора IN
        },
        'order': {
            'ID': 'DESC'
        },
        'select': ['OWNER_ID', 'STAGE_ID', 'CREATED_TIME']
    }

    all_stage_changes = []
    start = 0

    while True:
        params['start'] = start
        data = call_api(STAGE_HISTORY_METHOD, params=params, http_method='POST')

        # Проверяем, что ответ содержит ключи 'result' и 'items'
        if data and 'result' in data and 'items' in data['result']:
            stage_changes = data['result']['items']  # Извлекаем элементы из 'items'
            all_stage_changes.extend(stage_changes)

            if 'next' in data:
                start = data['next']
            else:
                break
        else:
            print("Ошибка при получении истории стадий сделок.")
            break

    return all_stage_changes


def check_deal_not_moved():
    """
    Проверка сделок, которые не были переведены по воронке в течение 6 часов после завершения последнего действия.
    """
    activities = get_deals_with_recent_activities()
    print(f"[Проверка 3] Сделок с завершенными активностями за последние 3 дня до 6 часов назад: {len(activities)}")

    if not activities:
        print("Нет сделок с завершенными активностями в указанном интервале.")
        return []

    deal_ids = [activity['OWNER_ID'] for activity in activities]  # Преобразуем множество в список

    # Получаем изменения стадии для всех сделок
    stage_changes = get_stage_changes_for_deals(deal_ids)


    deals_not_moved = []
    rows_to_add = []  # Для записи данных в Google Sheets

    timezone = pytz.timezone('Europe/Moscow')
    now = datetime.now(timezone)

    # Преобразуем список изменений стадий в словарь по deal_id для быстрого доступа
    last_stage_change_by_deal = {}
    for change in stage_changes:
        deal_id = change['OWNER_ID']
        last_stage_change_time_str = change['CREATED_TIME']
        try:
            last_stage_change_time = datetime.strptime(last_stage_change_time_str, '%Y-%m-%dT%H:%M:%S%z')
            if deal_id not in last_stage_change_by_deal:
                last_stage_change_by_deal[deal_id] = last_stage_change_time
        except ValueError:
            print(f"Неверный формат даты для сделки ID {deal_id}: {last_stage_change_time_str}")

    for activity in activities:
        deal_id = activity['OWNER_ID']
        end_time_str = activity['END_TIME']
        responsible_id = activity['RESPONSIBLE_ID']

        # Преобразуем END_TIME в datetime
        try:
            end_time = datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M:%S%z')
        except ValueError:
            print(f"Неверный формат даты для активности по сделке ID {deal_id}: {end_time_str}")
            continue

        # Проверяем, было ли изменение стадии после последней активности
        last_stage_change_time = last_stage_change_by_deal.get(deal_id)

        if last_stage_change_time:
            # Проверяем, прошло ли более 6 часов с момента завершения действия
            time_since_last_activity = now - end_time.astimezone(timezone)

            if time_since_last_activity > timedelta(hours=6) and last_stage_change_time < end_time:
                # Если стадия не менялась после действия
                deals_not_moved.append({
                    'deal_id': deal_id,
                    'responsible_id': responsible_id,
                    'last_activity_time': end_time_str,
                    'last_stage_change_time': last_stage_change_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'hours_since_completion': time_since_last_activity.total_seconds() / 3600
                })

    print(f"Сделок, не переведенных по воронке в течение 6 часов после последнего действия: {len(deals_not_moved)}")

    if deals_not_moved:
        # Получаем имена ответственных
        user_ids = [item['responsible_id'] for item in deals_not_moved]
        user_names = get_user_names(user_ids)

        # Выводим информацию и добавляем строки для записи в Google Sheets
        print("\nСписок таких сделок:")
        for item in deals_not_moved:
            responsible_name = user_names.get(item['responsible_id'], f"ID {item['responsible_id']}")
            remark = f"Сделка не была переведена по воронке в течение 6 часов после последнего действия"
            
            # Печатаем в терминал
            print(f"Сделка ID: {item['deal_id']}, Ответственный: {responsible_name}, Последнее действие: {item['last_activity_time']}, Последнее изменение стадии: {item['last_stage_change_time']}, Часов с момента последнего действия: {item['hours_since_completion']:.2f}")
            
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
        print("Все сделки были переведены по воронке в течение 6 часов после последнего действия.")

    # Если есть строки для добавления в Google Sheets
    if rows_to_add:
        write_to_sheet(rows_to_add)

    # Возвращаем список для дальнейшей обработки, если потребуется
    return deals_not_moved
