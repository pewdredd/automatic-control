import config
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE = config.DATABASE

# Формируем строку подключения к базе данных PostgreSQL
DATABASE_URL = f"postgresql://{DATABASE['USER']}:{DATABASE['PASSWORD']}@{DATABASE['HOST']}:{DATABASE['PORT']}/{DATABASE['NAME']}"

# Создаем подключение к базе данных через SQLAlchemy
engine = create_engine(DATABASE_URL)

# Создаем базовый класс для определения моделей
Base = declarative_base()

# Создаем сессию для работы с базой данных
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Функция для получения сессии (ее будем импортировать в других модулях)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Вызов функции для создания всех таблиц в базе данных, если еще не созданы
def create_tables():
    Base.metadata.create_all(bind=engine)
