from sqlalchemy import text
from sqlmodel import SQLModel, Session, create_engine
from .config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
    migrate_sqlite_schema()


def migrate_sqlite_schema() -> None:
    """Tiny dev migration for existing SQLite databases.

    SQLModel.create_all() creates missing tables, but it does not add new
    columns to existing tables. This keeps existing local data/app.db files
    working after adding User.is_admin.
    """
    if not settings.database_url.startswith("sqlite"):
        return

    with engine.begin() as connection:
        columns = connection.execute(text("PRAGMA table_info(user)")).mappings().all()
        if columns and "is_admin" not in {column["name"] for column in columns}:
            connection.execute(
                text("ALTER TABLE user ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0")
            )


def get_session():
    with Session(engine) as session:
        yield session
