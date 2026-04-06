"""Database configuration for backend services."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import declarative_base, sessionmaker


load_dotenv()


def _build_database_url() -> str:
    explicit_url = os.getenv("DATABASE_URL", "").strip()
    if explicit_url:
        return explicit_url

    user = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD", "")
    host = os.getenv("MYSQL_HOST", "127.0.0.1")
    port = os.getenv("MYSQL_PORT", "3306")
    database = os.getenv("MYSQL_DATABASE", "resume_ranker")
    return URL.create(
        drivername="mysql+pymysql",
        username=user,
        password=password,
        host=host,
        port=int(port),
        database=database,
    ).render_as_string(hide_password=False)


DATABASE_URL = _build_database_url()
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def ensure_database_ready() -> None:
    """Create tables if they do not exist yet."""
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
