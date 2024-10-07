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

def write_to_sheet(data):
    """
    Запись данных в Google Sheets в нужном формате.
    """
    sheet = get_google_sheet()
    
    # Записываем данные в лист, начиная с первой свободной строки
    sheet.append_rows(data, value_input_option='RAW')
