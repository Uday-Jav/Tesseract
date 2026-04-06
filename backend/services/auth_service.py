"""Business logic for auth endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from backend.models import PasswordResetToken, User
from backend.security import create_access_token, generate_reset_token, hash_password, verify_password


def register_user(db: Session, *, full_name: str, email: str, password: str) -> dict:
    normalized_email = email.strip().lower()
    if db.query(User).filter(User.email == normalized_email).first():
        raise ValueError("An account with this email already exists.")

    user = User(
        full_name=full_name.strip(),
        email=normalized_email,
        hashed_password=hash_password(password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "message": "Account created successfully.",
        "user": {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
        },
    }


def login_user(db: Session, *, email: str, password: str) -> dict:
    normalized_email = email.strip().lower()
    user = db.query(User).filter(User.email == normalized_email).first()
    if user is None or not verify_password(password, user.hashed_password):
        raise ValueError("Invalid email or password.")

    return {
        "message": "Login successful.",
        "access_token": create_access_token(user.email),
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
        },
    }


def create_password_reset(db: Session, *, email: str) -> dict:
    normalized_email = email.strip().lower()
    user = db.query(User).filter(User.email == normalized_email).first()
    if user is None:
        raise ValueError("No account found with this email.")

    token = generate_reset_token()
    record = PasswordResetToken(
        email=normalized_email,
        token=token,
        expires_at=datetime.utcnow() + timedelta(minutes=30),
    )
    db.add(record)
    db.commit()

    return {
        "message": "Password reset token generated.",
        "email": normalized_email,
        "reset_token": token,
        "expires_in_minutes": 30,
    }


def reset_password(db: Session, *, token: str, new_password: str) -> dict:
    record = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token == token, PasswordResetToken.used.is_(False))
        .first()
    )
    if record is None:
        raise ValueError("Reset token is invalid.")

    if record.expires_at < datetime.utcnow():
        raise ValueError("Reset token has expired.")

    user = db.query(User).filter(User.email == record.email).first()
    if user is None:
        raise ValueError("No account found for this reset token.")

    user.hashed_password = hash_password(new_password)
    record.used = True
    db.commit()
    return {"message": "Password updated successfully."}
