from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import config
from app.models import Base

engine = create_engine(config.DATABASE_URL, echo=True, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_tables():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()