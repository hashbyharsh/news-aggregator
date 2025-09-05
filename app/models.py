from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class Article(Base):
    __tablename__ = "articles"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=True)
    processed_content = Column(Text, nullable=True)
    source_url = Column(String(1000), nullable=False)
    group_id = Column(String(50), nullable=True)
    processed = Column(Boolean, default=False)
    brand_name = Column(String(100), nullable=True)
    model_name = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)