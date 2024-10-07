from sqlalchemy import Column, Integer, String, Boolean
from database import Base  # Импортируем Base из database.py

# Определяем модели таблиц базы данных
class DiffAssignmentID(Base):
    __tablename__ = 'diff_assigment_id'

    deal_id = Column(Integer, primary_key=True, index=True)
    fixed_time = Column(String)
    checked = Column(Boolean)

class AllCreatedDeal(Base):
    __tablename__ = 'all_created_deal'

    deal_id = Column(Integer, primary_key=True, index=True)
    contact_id = Column(Integer)
    created_time = Column(String)

class DelDealsContact(Base):
    __tablename__ = 'del_deals_contact'

    deal_id = Column(Integer, primary_key=True, index=True)
