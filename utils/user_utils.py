from bitrix24_api import call_api

def get_user_names(user_ids):
    """
    Функция для получения имен пользователей по их ID.
    """
    user_names = {}
    unique_user_ids = list(set(user_ids))
    batch_size = 50  # Ограничение на количество элементов в одном запросе (зависит от ограничений API)

    # Получаем данные о пользователях батчами по batch_size ID за один запрос
    for i in range(0, len(unique_user_ids), batch_size):
        batch_ids = unique_user_ids[i:i + batch_size]
        params = {'ID': batch_ids}
        data = call_api('user.get', params=params, http_method='POST')
        
        if data and 'result' in data and data['result']:
            users = data['result']
            for user in users:
                user_id = user.get('ID')
                user_names[user_id] = f"{user.get('NAME', '')} {user.get('LAST_NAME', '')}"
        else:
            print(f"Не удалось получить данные для пользователей: {batch_ids}")
            # Если не удалось получить данные, сохраняем ID как fallback
            for user_id in batch_ids:
                user_names[user_id] = f"ID {user_id}"

    return user_names
