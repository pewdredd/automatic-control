from bitrix24_api import call_api
from utils import *
from database import get_db

def check_contact_removal():
    """
    Проверка удаления контактов из сделок. Если контакт удален, выводит данные о сделке и ответственном,
    затем удаляет все записи из таблицы all_created_deal.
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
                print(f"Ответственный за сделку: {responsible_id}")
                print(f"Данные о сделке: {deal_data}")

        # Если проверка завершена успешно, выводим сообщение
        print("Успешная проверка")
    
    finally:
        db.close()
