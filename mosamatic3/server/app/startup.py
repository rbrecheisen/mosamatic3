from sqlmodel import Session, select
from .services.authservice import hash_password
from .config import settings
from .data.database import create_db_and_tables, engine
from .data.models import User


def read_admin_password() -> str:
    password_file = settings.admin_password_file
    if not password_file.exists():
        raise RuntimeError("File with admin password does not exist")
    password = password_file.read_text(encoding="utf-8").strip()
    if not password:
        raise RuntimeError("Could not load admin password")
    return password


def ensure_admin_user() -> None:
    admin_password = read_admin_password()
    with Session(engine) as session:
        admin = session.exec(
            select(User).where(User.email == settings.admin_username)
        ).first()
        admin_hash = hash_password(admin_password)
        if admin is None:
            admin = User(
                email=settings.admin_username,
                hashed_password=admin_hash,
                is_admin=True,
            )
            session.add(admin)
        else:
            admin.hashed_password = admin_hash
            admin.is_admin = True
            admin.is_active = True
            session.add(admin)
        session.commit()


def on_startup() -> None:
    create_db_and_tables()
    ensure_admin_user()