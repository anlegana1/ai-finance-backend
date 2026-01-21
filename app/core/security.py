import hashlib
import os
from typing import Tuple
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session, select
from jose.exceptions import ExpiredSignatureError, JWTError

from ..database import get_session
from ..models.user import User
from .jwt import decode_access_token


ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 100_000
SALT_BYTES = 16


def _pbkdf2_hash(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)


def hash_password(password: str) -> str:
    salt = os.urandom(SALT_BYTES)
    digest = _pbkdf2_hash(password, salt)
    return f"{ALGORITHM}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        stored = stored.strip()
        algorithm, salt_hex, hash_hex = stored.split("$")
        if algorithm != ALGORITHM:
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
        candidate = _pbkdf2_hash(password, salt)
        return candidate == expected
    except Exception:
        return False


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> User:
    # Default response for invalid tokens
    def _raise_invalid(detail: str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(token)
    except ExpiredSignatureError:
        _raise_invalid("Token expired")
    except JWTError:
        _raise_invalid("Invalid token")
    except Exception:
        _raise_invalid("Could not validate credentials")

    sub = payload.get("sub")
    if sub is None:
        _raise_invalid("Invalid token: missing subject")
    try:
        user_id = uuid.UUID(str(sub))
    except Exception:
        _raise_invalid("Invalid token: bad subject format")

    user = session.exec(select(User).where(User.id == user_id)).first()
    if user is None:
        _raise_invalid("User not found")
    return user

