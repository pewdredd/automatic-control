from datetime import datetime, timedelta
import pytz
from bitrix24_api import call_api
from utils import *

from datetime import datetime, timedelta
import pytz

def get_contacts_without_name():
    """
    Функция для получения контактов без заполненного имени, созданных за последние 6 часов.
    """
    CONTACTS_METHOD = 'crm.contact.list'

    # Получаем текущее время и вычитаем 6 часов
    timezone = pytz.timezone('Europe/Moscow')
    now = datetime.now(timezone)
    six_hours_ago = now - timedelta(hours=6)
    
    # Преобразуем дату в строку в формате ISO 8601 для запроса
    six_hours_ago_str = six_hours_ago.strftime('%Y-%m-%dT%H:%M:%S%z')

    # Параметры запроса
    params = {
        'filter': {
            'NAME': 'Без имени',  # Имя не указано
            '!PHONE': '',         # У контакта есть телефон
            '>=DATE_CREATE': six_hours_ago_str  # Созданы за последние 6 часов
        },
        'select': ['ID', 'NAME', 'LAST_NAME', 'PHONE', 'ASSIGNED_BY_ID', 'CREATED_BY_ID']
    }

    all_contacts = []
    start = 0

    while True:
        params['start'] = start
        data = call_api(CONTACTS_METHOD, params=params, http_method='POST')

        if data and 'result' in data:
            contacts = data['result']
            all_contacts.extend(contacts)

            if 'next' in data:
                start = data['next']
            else:
                break
        else:
            break

    return all_contacts


def get_calls_for_contacts(contact_ids):
    """
    Функция для получения всех завершенных исходящих звонков за последние 24 часа
    для списка контактов.
    """
    ACTIVITIES_METHOD = 'crm.activity.list'

    params = {
        'filter': {
            'TYPE_ID': 2,           # Тип активности: звонок
            'DIRECTION': 2,         # Направление: исходящий звонок
            'COMPLETED': 'Y',       # Завершенные звонки
            '>=START_TIME': (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%S%z'),
            'COMMUNICATIONS.ENTITY_ID': contact_ids  # Фильтр по контактам
        },
        'order': {
            'START_TIME': 'ASC'     # Сортируем по времени начала (от старых к новым)
        },
        'select': ['ID', 'START_TIME', 'RESPONSIBLE_ID', 'COMMUNICATIONS']
    }

    all_calls = []
    start = 0
    while True:
        params['start'] = start
        data = call_api(ACTIVITIES_METHOD, params=params, http_method='POST')

        if data and 'result' in data and data['result']:
            activities = data['result']
            all_calls.extend(activities)

            if 'next' in data:
                start = data['next']
            else:
                break
        else:
            break

    return all_calls


def check_contact_name_missing():
    """
    Проверка контактов, у которых не заполнено имя клиента и прошло более 3 часов с момента первого звонка.
    Записывает ссылку на контакт и информацию об ответственном и создателе в CRM таблицу.
    """
    contacts = get_contacts_without_name()
    print(f"[Проверка 4] Контактов без имени: {len(contacts)}")

    if not contacts:
        print("Нет контактов без имени.")
        return []

    # Собираем все контактные ID
    contact_ids = [contact['ID'] for contact in contacts]

    # Получаем все звонки для контактов за последние 24 часа
    calls = get_calls_for_contacts(contact_ids)

    # Группируем звонки по контактам
    calls_by_contact = {}
    for call in calls:
        communications = call.get('COMMUNICATIONS', [])
        for comm in communications:
            if comm.get('ENTITY_TYPE_ID') == '3':  # Контакты
                contact_id = comm.get('ENTITY_ID')
                if contact_id not in calls_by_contact:
                    calls_by_contact[contact_id] = []
                calls_by_contact[contact_id].append(call)

    contacts_to_notify = []
    rows_to_add = []  # Для записи данных в Google Sheets

    timezone = pytz.timezone('Europe/Moscow')
    now = datetime.now(timezone)

    for contact in contacts:
        contact_id = contact['ID']
        phone_numbers = contact.get('PHONE', [])

        # Пропускаем контакт, если нет номера телефона
        if not phone_numbers:
            continue

        assigned_by_id = contact.get('ASSIGNED_BY_ID')
        created_by_id = contact.get('CREATED_BY_ID')

        # Ищем первый исходящий звонок для контакта
        contact_calls = calls_by_contact.get(contact_id, [])
        if contact_calls:
            first_call = contact_calls[0]  # Звонки уже отсортированы по времени
            first_call_time_str = first_call.get('START_TIME')

            try:
                first_call_time = datetime.strptime(first_call_time_str, '%Y-%m-%dT%H:%M:%S%z')
                time_since_first_call = now - first_call_time.astimezone(timezone)

                if time_since_first_call > timedelta(hours=3):
                    contacts_to_notify.append({
                        'contact_id': contact_id,
                        'phone_numbers': [phone['VALUE'] for phone in phone_numbers],
                        'first_call_time': first_call_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'hours_since_first_call': time_since_first_call.total_seconds() / 3600,
                        'assigned_by_id': assigned_by_id,
                        'created_by_id': created_by_id
                    })
            except ValueError:
                print(f"Неверный формат даты для звонка контакта ID {contact_id}: {first_call_time_str}")
                continue
        else:
            # Если звонков не было, пропускаем контакт
            continue

    print(f"Контактов без имени, у которых прошло более 3 часов с момента первого звонка: {len(contacts_to_notify)}")

    if contacts_to_notify:
        # Собираем уникальные ID пользователей
        user_ids = set()
        for item in contacts_to_notify:
            if item['assigned_by_id']:
                user_ids.add(item['assigned_by_id'])
            if item['created_by_id']:
                user_ids.add(item['created_by_id'])

        # Получаем имена пользователей
        user_names = get_user_names(list(user_ids))

        # Выводим информацию и добавляем строки для записи в Google Sheets
        print("\nСписок таких контактов:")
        for item in contacts_to_notify:
            assigned_by_id = item['assigned_by_id']
            created_by_id = item['created_by_id']
            assigned_by_name = user_names.get(assigned_by_id, f"ID {assigned_by_id}")
            created_by_name = user_names.get(created_by_id, f"ID {created_by_id}")

            remark = "Контакт без имени и прошло более 3 часов с момента первого звонка"

            # Формируем ссылку на профиль контакта
            contact_link = f"https://kubnov.bitrix24.ru/crm/contact/details/{item['contact_id']}/"

            print(
                f"Контакт ID: {item['contact_id']}, "
                f"Телефон: {', '.join(item['phone_numbers'])}, "
                f"Первый звонок: {item['first_call_time']}, "
                f"Часов с момента первого звонка: {item['hours_since_first_call']:.2f}, "
                f"Ответственный: {assigned_by_name} (ID {assigned_by_id}), "
                f"Создал: {created_by_name} (ID {created_by_id})"
            )

            # Формируем строку для записи в Google Sheets
            row = [
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),  # Текущая дата и время
                "Program",
                item['contact_id'],
                "",  # Название контакта (если требуется)
                "",  # Статус контакта (если требуется)
                assigned_by_name,
                contact_link,  # Ссылка на профиль контакта
                remark
            ]
            rows_to_add.append(row)
    else:
        print("Нет контактов, соответствующих условиям.")

    # Если есть строки для добавления в Google Sheets
    if rows_to_add:
        write_to_sheet(rows_to_add)

    # Возвращаем список для дальнейшей обработки, если потребуется
    return contacts_to_notify
