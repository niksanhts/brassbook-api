from datetime import datetime, timedelta
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.data.schemas import TokenData
from app.data.repositories.users_repository import UserRepository
from app.config import settings
from app.dependencies import get_user_repo

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v2/auth/token")


def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str):
    return pwd_context.hash(password)


async def authenticate_user(
        email: str,
        password: str,
        repo: UserRepository
):
    user = await repo.get_user_by_email(email)

    # Исправлено обращение к hashed_password
    if not user or not verify_password(password, user.hashed_password):
        return None

    # Проверка активности пользователя
    if not user.is_active:
        raise HTTPException(
            status_code=400,
            detail="User inactive"
        )
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


async def get_current_user(
        token: Annotated[str, Depends(oauth2_scheme)],
        repo: Annotated[UserRepository, Depends(get_user_repo)],
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception

    user = await repo.get_user_by_email(email=token_data.email)
    if user is None:
        raise credentials_exception
    return user