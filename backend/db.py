import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

if os.getenv("TESTING"):
    DATABASE_URL = os.getenv(
        "DATABASE_URL", "postgresql://akvo:password@db:5432/logbook"
    ).replace("logbook", "logbook_test")
else:
    DATABASE_URL = os.getenv(
        "DATABASE_URL", "postgresql://akvo:password@db:5432/logbook"
    )

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
