"""数据库引擎与会话。"""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """建表（开发用；生产建议 Alembic 迁移）。"""
    from app import models  # noqa: F401  确保模型被导入注册

    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns()


# 轻量"自动迁移"：给已存在的表补充新增列（仅 SQLite，开发期免删库）。
_EXPECTED_COLUMNS = {
    "documents": [("content_hash", "VARCHAR(64)")],
    "bookings": [("system_note", "VARCHAR(256)")],
}


def _ensure_sqlite_columns() -> None:
    if not settings.database_url.startswith("sqlite"):
        return
    with engine.begin() as conn:
        for table, columns in _EXPECTED_COLUMNS.items():
            rows = conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
            if not rows:
                continue
            existing = {r[1] for r in rows}
            for name, ddl in columns:
                if name not in existing:
                    conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
