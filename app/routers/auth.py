import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import SQLModel, Field, Session, select
from pydantic import EmailStr

from ..database import get_session
from ..models.user import User
from ..core.security import hash_password, verify_password
from ..core.jwt import create_access_token


router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)


class RegisterIn(SQLModel):
    email: EmailStr = Field(index=False)
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
    if any(c.isspace() for c in payload.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña no debe contener espacios",
        )
    email_norm = payload.email.strip().lower()
    exists_stmt = select(User).where(User.email == email_norm)
    existing = session.exec(exists_stmt).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    now = datetime.utcnow()
    user = User(
        id=uuid.uuid4(),
        email=email_norm,
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
    email: EmailStr
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
    if any(c.isspace() for c in payload.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña no debe contener espacios",
        )
    email_norm = payload.email.strip().lower()
    stmt = select(User).where(User.email == email_norm)
    user = session.exec(stmt).first()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Include subject as user id and optionally email
    token = create_access_token({"sub": str(user.id), "email": user.email})
    return TokenOut(access_token=token, token_type="bearer")


@router.post(
    "/token",
    response_model=TokenOut,
    status_code=status.HTTP_200_OK,
)
def token(form_data: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_session)):
    # OAuth2PasswordRequestForm usa 'username' como el campo de email
    email_norm = form_data.username.strip().lower()
    if any(c.isspace() for c in form_data.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña no debe contener espacios",
        )
    user = session.exec(select(User).where(User.email == email_norm)).first()
    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = create_access_token({"sub": str(user.id), "email": user.email})
    return TokenOut(access_token=token, token_type="bearer")

