from datetime import datetime, timedelta
import pytz
from bitrix24_api import call_api
from utils import *
from sqlalchemy.orm import Session
from database import get_db


TIMEZONE = pytz.timezone('Europe/Moscow')

def check_additional_phone_number():
    """
    Проверяет, внесен ли дополнительный номер клиента в течение одного часа после первого звонка клиенту.
    Если номер не внесен, выводит информацию о сделке и ответственном и записывает данные в Google Sheets.
    """
    print('[Проверка 7]')
    rows_to_add = []  # Для записи данных в Google Sheets

    # Текущее время в часовом поясе Москвы
    current_time = datetime.now(TIMEZONE)

    # Создаем сессию базы данных
    db = next(get_db())

    try:
        # Получаем все deal_id и время создания из all_created_deal
        deals = db.query(AllCreatedDeal.deal_id, AllCreatedDeal.created_time).all()

        # Проверяем каждую сделку
        for deal in deals:
            deal_id = deal.deal_id
            created_time_str = deal.created_time
            created_time = datetime.fromisoformat(created_time_str).astimezone(TIMEZONE)

            # Получаем информацию о первом звонке
            activity_params = {
                "filter": {
                    "OWNER_ID": deal_id,
                    "OWNER_TYPE_ID": 2,  # Тип ID для сделки в Bitrix24
                    "TYPE_ID": 2,  # Тип активности (2 = звонок в Bitrix24)
                    "COMPLETED": "Y"  # Только завершенные звонки
                },
                "order": {
                    "END_TIME": "ASC"  # Сортируем по времени завершения, чтобы получить первый звонок
                },
                "select": ["ID", "END_TIME"]
            }

            # Запрос на получение списка активностей
            activities_response = call_api('crm.activity.list', activity_params, 'POST')

            # Проверяем, был ли первый завершенный звонок
            if activities_response and 'result' in activities_response and len(activities_response['result']) > 0:
                # Получаем время первого звонка
                first_call_time_str = activities_response['result'][0].get('END_TIME')
                first_call_time = datetime.fromisoformat(first_call_time_str).astimezone(TIMEZONE)

                # Проверяем, прошел ли час с момента первого звонка
                if current_time - first_call_time > timedelta(hours=1):
                    # Получаем данные о сделке с помощью call_api
                    deal_params = {
                        "id": deal_id
                    }
                    deal_response = call_api('crm.deal.get', deal_params)

                    if deal_response and 'result' in deal_response:
                        deal_info = deal_response['result']
                        contact_id = deal_info.get('CONTACT_ID')
                        responsible_id = deal_info.get('ASSIGNED_BY_ID')

                        # Проверяем, есть ли контакт у сделки
                        if contact_id:
                            # Получение информации о контакте с помощью call_api
                            contact_params = {
                                "id": contact_id
                            }
                            
                            # Запрос на получение информации о контакте
                            contact_response = call_api('crm.contact.get', contact_params)

                            # Проверка данных о контакте
                            if contact_response and 'result' in contact_response:
                                contact_info = contact_response['result']
                                phones = contact_info.get('PHONE', [])

                                # Проверяем количество номеров телефона
                                if len(phones) > 1:
                                    print(f"Сделка ID: {deal_id} имеет более одного номера телефона.")
                                else:
                                    print(f"Сделка ID: {deal_id} имеет только один номер телефона.")
                                    print(f"Ответственный за сделку (ID): {responsible_id}")
                                    
                                    # Получаем имя ответственного
                                    user_name = get_user_names([responsible_id]).get(responsible_id, f"ID {responsible_id}")
                                    
                                    # Формируем ссылку на сделку
                                    deal_link = f"https://kubnov.bitrix24.ru/crm/deal/details/{deal_id}/"

                                    # Формируем замечание для Google Sheets
                                    remark = "Дополнительный номер не внесен в течение часа после первого звонка"
                                    
                                    # Формируем строку для записи в Google Sheets
                                    row = [
                                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),  # Текущая дата и время
                                        "Program",
                                        deal_id,
                                        deal_info.get('TITLE', ""),  # Название сделки
                                        deal_info.get('STAGE_ID', ""),  # Статус сделки
                                        user_name,
                                        deal_link,  # Ссылка на сделку
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
                                print(f"Ошибка при запросе информации о контакте {contact_id}.")
                        else:
                            print(f"Контакт для сделки ID {deal_id} не найден.")
                    else:
                        print(f"Ошибка при запросе информации о сделке {deal_id}.")
            else:
                print(f"Для сделки ID {deal_id} не найден завершенный звонок.")

        # Если есть строки для добавления в Google Sheets
        if rows_to_add:
            write_to_sheet(rows_to_add)

        print("Успешная проверка")

    finally:
        db.close()
