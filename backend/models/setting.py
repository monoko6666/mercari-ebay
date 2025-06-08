from sqlalchemy import Column, String, Float
from ..database import Base

class Setting(Base):
    __tablename__ = "settings"

    key = Column(String, primary_key=True, index=True)
    value = Column(Float) # 数値を保存するためFloat型を使用