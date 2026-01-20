from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from jose import JWTError, jwt

from ..config import settings


ACCESS_TOKEN_EXPIRE_MINUTES = 30


def create_access_token(data: Dict[str, Any]) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"iat": int(now.timestamp()), "exp": int(expire.timestamp())})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return encoded_jwt


def decode_access_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError as e:
        raise e

