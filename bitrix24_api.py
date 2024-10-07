import requests
from config import WEBHOOK_URL

def call_api(method, params=None, http_method='GET'):
    """
    Универсальная функция для вызова методов API Bitrix24.
    """
    url = f"{WEBHOOK_URL}{method}"

    try:
        if http_method == 'GET':
            response = requests.get(url, params=params)
        elif http_method == 'POST':
            response = requests.post(url, json=params)
        else:
            raise ValueError("Недопустимый метод HTTP.")
        
        response.raise_for_status()
        data = response.json()
        return data
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP ошибка: {http_err}")
        print("Детали ошибки:", response.text)
        return None
    except Exception as err:
        print(f"Другая ошибка: {err}")
        return None
