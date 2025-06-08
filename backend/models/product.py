from sqlalchemy import Column, String, Integer, Float, Text
from ..database import Base

class Product(Base):
    __tablename__ = "products"

    id = Column(String, primary_key=True, index=True)
    mercari_url = Column(Text)
    title_jp = Column(Text)
    title_en = Column(Text)
    description_jp = Column(Text)
    description_en = Column(Text)
    price_jpy = Column(Integer)
    price_usd = Column(Float)
    condition_mercari = Column(String)
    condition_ebay_id = Column(Integer)
    category_id = Column(String)
    images = Column(Text)
    stock_status = Column(String)
    profit_rate = Column(Float)
    shipping_cost = Column(Integer)
    exchange_rate = Column(Float)
