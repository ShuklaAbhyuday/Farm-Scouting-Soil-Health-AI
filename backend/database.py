from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import settings


def _normalize_db_url(raw_url: str) -> str:
    url = (raw_url or "sqlite:///./farm_scout.db").strip()
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


SQLALCHEMY_DATABASE_URL = _normalize_db_url(settings.DATABASE_URL)
_connect_args = {"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args=_connect_args,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    if SQLALCHEMY_DATABASE_URL.startswith("sqlite:///"):
        from backend.migrations.phase1_migration import migrate_sqlite_db
        from backend.migrations.phase2_migration import migrate_phase2_sqlite
        db_path = SQLALCHEMY_DATABASE_URL.replace("sqlite:///", "", 1)
        if db_path and db_path != ":memory:":
            migrate_sqlite_db(db_path)
            migrate_phase2_sqlite(db_path)
