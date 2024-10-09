from datetime import datetime
from bitrix24_api import call_api
from utils import *
from database import get_db

def check_contact_removal():
    """
    Проверка удаления контактов из сделок. Если контакт удален, выводит данные о сделке и ответственном,
    затем удаляет все записи из таблицы all_created_deal. Также записывает ссылку на сделку.
    """
    print('[Проверка 6]')

    # Создаем сессию базы данных
    db = next(get_db())
    
    try:
        # Получаем все записи из таблицы all_created_deal, где contact_id не NULL
        deals = db.query(AllCreatedDeal.deal_id, AllCreatedDeal.contact_id).filter(AllCreatedDeal.contact_id != None).all()
        
        # Собираем все deal_ids для единого запроса
        deal_ids = [deal.deal_id for deal in deals]

        # Получаем данные о сделках одним запросом
        deals_data = {}
        if deal_ids:
            deals_data_list = get_deal_data(deal_ids)
            deals_data = {str(deal['ID']): deal for deal in deals_data_list}  # Convert deal['ID'] to string

        rows_to_add = []  # Для записи данных в Google Sheets
        
        # Проверяем данные по каждой сделке
        for deal in deals:
            deal_id = deal.deal_id
            deal_data = deals_data.get(str(deal_id), {})  # Convert deal_id to string
            
            # Получаем информацию о текущем контакте и ответственном
            current_contact_id = deal_data.get('CONTACT_ID')
            responsible_id = deal_data.get('ASSIGNED_BY_ID')

            # Если contact_id отсутствует, выводим данные о сделке и ответственном
            if current_contact_id is None:
                print(f"Контакт был удален из сделки ID: {deal_id}")
                responsible_name = get_user_names([responsible_id]).get(responsible_id, f"ID {responsible_id}")

                # Формируем ссылку на сделку
                deal_link = f"https://kubnov.bitrix24.ru/crm/deal/details/{deal_id}/"

                print(f"Ответственный за сделку: {responsible_name}")
                print(f"Данные о сделке: {deal_data}")

                # Формируем строку для записи в Google Sheets
                row = [
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),  # Текущая дата и время
                    "Program",
                    deal_id,
                    deal_data.get('TITLE', ""),  # Название сделки (если доступно)
                    deal_data.get('STAGE_ID', ""),  # Статус сделки (если доступно)
                    responsible_name,
                    deal_link,  # Ссылка на сделку
                    "Контакт был удален из сделки"
                ]
                rows_to_add.append(row)

        # Записываем данные в Google Sheets
        if rows_to_add:
            write_to_sheet(rows_to_add)

        # Если проверка завершена успешно, выводим сообщение
        print("Успешная проверка")
    
    finally:
        db.close()
