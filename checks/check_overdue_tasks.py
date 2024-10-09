from datetime import datetime, timedelta
import pytz
from bitrix24_api import call_api
from utils import *

def get_overdue_activities():
    """
    Функция для получения дел (активностей) внутри сделок CRM, которые просрочены более чем на 1 час.
    """
    ACTIVITIES_METHOD = 'crm.activity.list'

    # Определяем текущую дату и время, а также время час назад, используя часовой пояс Москвы
    timezone = pytz.timezone('Europe/Moscow')
    now = datetime.now(timezone)
    one_hour_ago = now - timedelta(hours=1)

    # Приводим дату к строковому формату ISO 8601, чтобы использовать в фильтре
    one_hour_ago_str = one_hour_ago.strftime('%Y-%m-%dT%H:%M:%S%z')

    # Параметры запроса для получения незавершенных дел с дедлайном больше чем час назад
    params = {
        'filter': {
            'COMPLETED': 'N',  # Только незавершенные дела
            '<=DEADLINE': one_hour_ago_str,  # С дедлайном раньше чем один час назад
            'OWNER_TYPE_ID': 2,  # Тип объекта - сделка (2 соответствует сделке)
            # В случае необходимости можно добавить фильтр по конкретной воронке
        },
        'select': ['ID', 'SUBJECT', 'DEADLINE', 'RESPONSIBLE_ID', 'CREATED', 'OWNER_ID', 'OWNER_TYPE_ID']
    }

    all_activities = []
    start = 0

    # Получаем все активности (постранично) пока не получим все
    while True:
        params['start'] = start
        data = call_api(ACTIVITIES_METHOD, params=params, http_method='POST')
        
        # Проверяем наличие результатов в ответе
        if data and 'result' in data and data['result']:
            activities = data['result']
            all_activities.extend(activities)

            # Если в ответе есть 'next', значит есть следующая страница
            if 'next' in data:
                start = data['next']
            else:
                break  # Если 'next' нет, значит данные закончились
        else:
            print("Ошибка при получении дел.")
            break

    return all_activities

def check_overdue_activities():
    """
    Проверка просроченных дел (активностей) внутри сделок и вывод результатов,
    запись ссылки и статуса сделки в CRM таблицу.
    """
    overdue_activities = get_overdue_activities()
    print(f"[Проверка 1] Просроченных дел более чем на 1 час: {len(overdue_activities)}")

    rows_to_add = []  # Список строк для записи в Google Sheets

    if overdue_activities:
        # Собираем ID всех ответственных пользователей
        user_ids = [activity['RESPONSIBLE_ID'] for activity in overdue_activities]
        user_names = get_user_names(user_ids)

        # Собираем ID всех сделок, к которым относятся просроченные активности
        deal_ids = [activity['OWNER_ID'] for activity in overdue_activities if activity['OWNER_TYPE_ID'] == '2']
        
        # Получаем информацию о сделках с использованием get_deal_data
        deals_data = get_deal_data(deal_ids)
        deal_info = {deal['ID']: deal for deal in deals_data}

        # Выводим список всех просроченных дел с подробной информацией
        print("\nСписок просроченных дел:")
        for activity in overdue_activities:
            responsible_id = activity['RESPONSIBLE_ID']
            responsible_name = user_names.get(responsible_id, f"ID {responsible_id}")
            deadline = activity['DEADLINE']
            subject = activity['SUBJECT']
            activity_id = activity['ID']
            deal_id = activity['OWNER_ID']
            
            # Получаем информацию о сделке
            deal_data = deal_info.get(deal_id, {'TITLE': f"ID {deal_id}", 'ASSIGNED_BY_ID': None, 'STAGE_ID': 'Unknown'})
            deal_title = deal_data['TITLE']
            deal_status = deal_data.get('STAGE_ID', 'Unknown')  # Получаем статус сделки
            
            # Формируем ссылку на сделку
            deal_link = f"https://kubnov.bitrix24.ru/crm/deal/details/{deal_id}/"

            # Формируем замечание
            remark = f"Дело просрочено более чем на 1 час. Дедлайн: {deadline}"

            print(f"Дело ID: {activity_id}, Тема: {subject}, Ответственный: {responsible_name}, Дедлайн: {deadline}, Сделка: {deal_title}, Статус: {deal_status}")

            # Подготовка строки для записи в Google Sheets
            row = [
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),  # Текущая дата и время
                "Program",
                deal_id,
                deal_title,  # Название сделки
                deal_status,  # Статус сделки
                responsible_name,
                deal_link,  # Ссылка на сделку
                remark
            ]
            rows_to_add.append(row)
    else:
        print("Нет просроченных дел.")

    # Если есть строки для добавления в Google Sheets
    if rows_to_add:
        write_to_sheet(rows_to_add)

    # Возвращаем список просроченных дел, если потребуется для последующей обработки
    return overdue_activities
