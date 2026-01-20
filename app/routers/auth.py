import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import SQLModel, Field, Session, select

from ..database import get_session
from ..models.user import User
from ..core.security import hash_password, verify_password
from ..core.jwt import create_access_token


router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)


class RegisterIn(SQLModel):
    email: str = Field(index=False)
    password: str = Field(min_length=6)


class UserRead(SQLModel):
    id: uuid.UUID
    email: str
    created_at: datetime
    updated_at: datetime


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
def register_user(
    payload: RegisterIn,
    session: Session = Depends(get_session),
):
    # Validar que el email no exista
    exists_stmt = select(User).where(User.email == payload.email)
    existing = session.exec(exists_stmt).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    now = datetime.utcnow()
    user = User(
        id=uuid.uuid4(),
        email=payload.email,
        hashed_password=hash_password(payload.password),
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )

    session.add(user)
    session.commit()
    session.refresh(user)
    return UserRead(
        id=user.id,
        email=user.email,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


class LoginIn(SQLModel):
    email: str
    password: str


class TokenOut(SQLModel):
    access_token: str
    token_type: str


@router.post(
    "/login",
    response_model=TokenOut,
    status_code=status.HTTP_200_OK,
)
def login(payload: LoginIn, session: Session = Depends(get_session)):
    stmt = select(User).where(User.email == payload.email)
    user = session.exec(stmt).first()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Include subject as user id and optionally email
    token = create_access_token({"sub": str(user.id), "email": user.email})
    return TokenOut(access_token=token, token_type="bearer")

