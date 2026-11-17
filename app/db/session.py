from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=False
    )

SessionLocal = sessionmaker(
    expire_on_commit=False, 
    autoflush=False,
    bind=engine
    )