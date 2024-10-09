import gspread
from oauth2client.service_account import ServiceAccountCredentials
from config import SHEET_NAME, WORKSHEET_NAME, CREDENTIALS_FILE

# Авторизация и получение листа Google Sheets
def get_google_sheet():
    """
    Авторизация и подключение к Google Sheets.
    """
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    credentials = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
    client = gspread.authorize(credentials)
    sheet = client.open(SHEET_NAME).worksheet(WORKSHEET_NAME)
    return sheet

def read_existing_rows(sheet):
    """
    Чтение всех существующих строк из Google Sheets.
    """
    existing_rows = sheet.get_all_values()
    # Пропускаем заголовки, если они есть
    return existing_rows[1:] if existing_rows else []

def write_to_sheet(data):
    """
    Запись данных в Google Sheets в нужном формате, если таких записей еще нет.
    """
    sheet = get_google_sheet()

    # Читаем уже существующие записи
    existing_rows = read_existing_rows(sheet)
    
    # Преобразуем существующие данные в набор для быстрого поиска
    existing_entries = set(
        tuple(row[1:]) for row in existing_rows
    )

    rows_to_write = []
    
    # Проверяем каждую новую строку
    for row in data:
        # Преобразуем новую запись в формат для сравнения
        new_entry = tuple(row[1:])  # Пропускаем первый столбец (дату)

        if new_entry not in existing_entries:
            rows_to_write.append(row)

    # Записываем только новые строки
    if rows_to_write:
        sheet.append_rows(rows_to_write, value_input_option='RAW')
    else:
        print("Нет новых данных для записи.")
