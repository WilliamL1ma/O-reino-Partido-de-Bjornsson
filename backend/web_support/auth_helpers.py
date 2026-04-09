from __future__ import annotations

from datetime import date, datetime

import bcrypt
from sqlalchemy import select


def normalize_email(email: str) -> str:
    return email.strip().lower()


def validate_birth_date(raw_value: str) -> date | None:
    try:
        parsed = datetime.strptime(raw_value, "%Y-%m-%d").date()
    except ValueError:
        return None
    if parsed >= date.today():
        return None
    return parsed


def password_is_strong(password: str) -> bool:
    return len(password) >= 8


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def get_user_by_email(email: str, *, session_scope, user_model):
    with session_scope() as db_session:
        return db_session.scalar(select(user_model).where(user_model.email == email))


def get_user_by_id(user_id: int, *, session_scope, user_model):
    with session_scope() as db_session:
        return db_session.get(user_model, user_id)


def get_character_by_user_id(user_id: int, *, session_scope, character_model):
    with session_scope() as db_session:
        return db_session.scalar(select(character_model).where(character_model.user_id == user_id))


def login_user(user, *, session) -> None:
    session["user_id"] = user.id
    session["username"] = user.username
    session["user_email"] = user.email


def logout_user(*, session) -> None:
    session.clear()
