from bitrix24_api import call_api

def get_deal_data(deal_ids):
    """
    Получает данные о сделках по их списку ID, включая всю необходимую информацию для записи в Google Sheets.
    """
    DEALS_METHOD = 'crm.deal.list'
    deal_data_list = []

    # Убираем дубликаты из списка ID
    unique_deal_ids = list(set(deal_ids))
    batch_size = 50  # Ограничение на количество элементов в одном запросе (ограничения API)

    # Получаем данные о сделках батчами по batch_size ID за один запрос
    for i in range(0, len(unique_deal_ids), batch_size):
        batch_ids = unique_deal_ids[i:i + batch_size]
        params = {
            'filter': {
                'ID': batch_ids
            },
            'select': [
                'ID',  # ID сделки
                'CONTACT_ID',  # ID контакта (если есть)
                'COMPANY_ID',  # ID компании (если есть)
                'ASSIGNED_BY_ID',  # ID ответственного
                'CREATED_BY_ID',  # ID создателя сделки
                'CATEGORY_ID',  # Категория (Филиал)
                'STAGE_ID',  # Стадия сделки (Отдел)
                'TITLE',  # Название сделки
                'DATE_CREATE',  # Дата создания
                'CLOSEDATE',  # Дата закрытия (планируемая)
            ]
        }
        response = call_api(DEALS_METHOD, params=params, http_method='POST')
        
        # Проверяем наличие результатов в ответе
        if response and 'result' in response:
            deals = response['result']
            for deal in deals:
                # Отфильтруем только нужные поля и добавим все необходимые для Google Sheets
                filtered_data = {
                    'ID': deal.get('ID'),
                    'CONTACT_ID': deal.get('CONTACT_ID'),
                    'COMPANY_ID': deal.get('COMPANY_ID'),
                    'ASSIGNED_BY_ID': deal.get('ASSIGNED_BY_ID'),
                    'CREATED_BY_ID': deal.get('CREATED_BY_ID'),
                    'CATEGORY_ID': deal.get('CATEGORY_ID'),
                    'STAGE_ID': deal.get('STAGE_ID'),
                    'TITLE': deal.get('TITLE'),
                    'DATE_CREATE': deal.get('DATE_CREATE'),
                    'CLOSEDATE': deal.get('CLOSEDATE'),
                }
                deal_data_list.append(filtered_data)
        else:
            print("Ошибка при получении информации о сделках.")
            continue

    return deal_data_list
