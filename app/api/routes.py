import asyncio
import logging
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.auth import verify_password
from app.dependencies import get_user_repo
from app.core.compare_melodies import compare_melodies
from app.config import settings
from app.data.database import get_db
from app.data.repositories.s3_repository import S3Repository
from app.data.repositories.users_repository import UserRepository
from app.api.file_validation import validate_file
from app.data.schemas import (
    UserCreate,
    UserResponse,
    UserUpdate,
    PasswordUpdate,
    Token,
    TokenData,
    #VerifyCode
)
from app.core.auth import (
    get_current_user,
    create_access_token,
    authenticate_user,
    #refresh_access_token,
    #verify_user,
    #send_verification_code
)

# Инициализация роутеров
compare_router = APIRouter(tags=["compare"])
auth_router = APIRouter(prefix="/v1/auth", tags=["auth"])
user_router = APIRouter(prefix="/v1/user", tags=["user"])
logger = logging.getLogger(__name__)


# Роуты для сравнения мелодий
@compare_router.post("/v1/compare_melodies")
async def compare_melodies_v1(
        file1: UploadFile = File(...),
        file2: UploadFile = File(...)
):
    """Сравнение мелодий (v1)"""
    return await _compare_melodies(file1, file2)

@compare_router.post("/v2/compare_melodies/file")
async def compare_melodies_v2(
        file1: UploadFile = File(...),
        file2: UploadFile = File(...)
):
    """Сравнение мелодий (v2)"""
    return await _compare_melodies(file1, file2)

async def _compare_melodies(file1: UploadFile, file2: UploadFile):
    """Общая логика сравнения мелодий"""
    logging.info("Начало сравнения мелодий")
    try:
        validate_file(file1)
        validate_file(file2)

        file1_content = await file1.read()
        file2_content = await file2.read()

        result = await asyncio.to_thread(compare_melodies, file1_content, file2_content)
        return {"result": result} if result else {"error": "Ошибка при сравнении мелодий"}

    except Exception as e:
        logger.error(f"Ошибка при сравнении мелодий: {str(e)}")
        return {"error": str(e)}


# Роуты для работы с пользователем
@user_router.get("/users/me", response_model=UserResponse)
async def read_current_user(
        current_user: Annotated[UserResponse, Depends(get_current_user)],
):
    """Получение информации о текущем пользователе"""
    return current_user

@user_router.put("/users/me", response_model=UserResponse)
async def update_user_info(
        user_data: UserUpdate,
        repo: Annotated[UserRepository, Depends(get_user_repo)],
        current_user: Annotated[UserResponse, Depends(get_current_user)],
):
    """Обновление информации о пользователе"""
    updated_user = await repo.update_user_info(current_user.id, user_data.dict(exclude_unset=True))
    if not updated_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")
    return updated_user

@user_router.put("/users/me/password", response_model=UserResponse)
async def update_user_password(
        password_data: PasswordUpdate,
        repo: Annotated[UserRepository, Depends(get_user_repo)],
        current_user: Annotated[UserResponse, Depends(get_current_user)],
):
    """Обновление пароля пользователя"""
    user = await repo.get_user_by_email(current_user.email)
    if not user or not verify_password(password_data.current_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Текущий пароль неверен",
        )
    updated_user = await repo.update_user_password(current_user.id, password_data.new_password)
    return updated_user

# Роуты для работы с аватаром
@user_router.post("/users/me/avatar", status_code=status.HTTP_200_OK)
async def upload_user_avatar(
        file: UploadFile,
        repo: Annotated[UserRepository, Depends(get_user_repo)],
        s3_repo: Annotated[S3Repository, Depends()],
        current_user: Annotated[UserResponse, Depends(get_current_user)],
):
    """Загрузка аватара пользователя"""
    await validate_file(file)
    file_ext = file.filename.split(".")[-1]
    object_name = f"avatars/{current_user.id}_{datetime.now().timestamp()}.{file_ext}"

    await s3_repo.upload_file(
        bucket="user-photos",
        object_name=object_name,
        file_data=file.file,
        content_type=file.content_type,
    )

    updated_user = await repo.update_user_info(
        current_user.id, {"avatar_url": object_name}
    )
    if not updated_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")
    avatar_url = await s3_repo.get_file_url("user-photos", object_name)
    return {"message": "Аватар успешно загружен", "avatar_url": avatar_url}

@user_router.get("/users/me/avatar")
async def get_user_avatar(
        repo: Annotated[UserRepository, Depends(get_user_repo)],
        s3_repo: Annotated[S3Repository, Depends()],
        current_user: Annotated[UserResponse, Depends(get_current_user)],
):
    """Получение URL аватара пользователя"""
    if not current_user.avatar_url:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Аватар не найден")
    avatar_url = await s3_repo.get_file_url(
        bucket="user-photos",
        object_name=current_user.avatar_url,
        expires=3600,
    )
    return {"avatar_url": avatar_url}

@user_router.delete("/users/me/avatar")
async def delete_user_avatar(
        repo: Annotated[UserRepository, Depends(get_user_repo)],
        s3_repo: Annotated[S3Repository, Depends()],
        current_user: Annotated[UserResponse, Depends(get_current_user)],
):
    """Удаление аватара пользователя"""
    if not current_user.avatar_url:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Аватар не найден")
    await s3_repo.delete_file("user-photos", current_user.avatar_url)
    await repo.update_user_info(current_user.id, {"avatar_url": None})
    return {"message": "Аватар успешно удален"}

# Аутентификация и регистрация
@auth_router.post("/registration", status_code=status.HTTP_201_CREATED)
async def register_user(
        user_data: UserCreate,
        repo: Annotated[UserRepository, Depends(get_user_repo)]
):
    """Регистрация нового пользователя"""
    existing_user = await repo.get_user_by_email(user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email уже зарегистрирован",
        )

    user = await repo.create_user(user_data)
    return {"message": "User created successfully", "user_id": user.id}


@auth_router.post("/login", response_model=Token)
async def login_for_access_token(
        form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
        repo: Annotated[UserRepository, Depends(get_user_repo)]
):
    """Авторизация и получение JWT токена"""
    user = await authenticate_user(form_data.username, form_data.password, repo)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
        )

    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {"access_token": access_token, "token_type": "bearer"}


@auth_router.post("/check")
async def check_token(
        current_user: Annotated[UserResponse, Depends(get_current_user)]
):
    """Проверка access token"""
    return {"valid": True, "user": current_user}

'''
@auth_router.put("/verifyuser")
async def verify_user_account(
        verify_data: VerifyCode,
        repo: Annotated[UserRepository, Depends(get_user_repo)]
):
    """Подтверждение пользователя по коду"""
    success = await verify_user(verify_data.email, verify_data.code, repo)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code",
        )
    return {"message": "User verified successfully"}




@auth_router.put("/sendcode")
async def send_verification_code_to_user(
        email: str,
        repo: Annotated[UserRepository, Depends(get_user_repo)]
):
    """Отправка кода подтверждения"""
    await send_verification_code(email, repo)
    return {"message": "Verification code sent"}


@auth_router.get("/refresh", response_model=Token)
async def refresh_token(
        current_user: Annotated[UserResponse, Depends(get_current_user)],
        repo: Annotated[UserRepository, Depends(get_user_repo)]
):
    """Обновление access token"""
    new_token = refresh_access_token(current_user, repo)
    return {"access_token": new_token, "token_type": "bearer"}
'''

# Профиль пользователя
@user_router.put("/registration")
async def update_user_password(
        password_data: PasswordUpdate,
        current_user: Annotated[UserResponse, Depends(get_current_user)],
        repo: Annotated[UserRepository, Depends(get_user_repo)]
):
    """Обновление пароля пользователя"""
    user = await repo.get_user_by_email(current_user.email)
    if not user or not verify_password(password_data.current_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Текущий пароль неверен",
        )

    await repo.update_user_password(current_user.id, password_data.new_password)
    return {"message": "Password updated successfully"}


@user_router.put("/")
async def update_user_info(
        user_data: UserUpdate,
        current_user: Annotated[UserResponse, Depends(get_current_user)],
        repo: Annotated[UserRepository, Depends(get_user_repo)]
):
    """Обновление данных пользователя"""
    updated_user = await repo.update_user_info(current_user.id, user_data.dict(exclude_unset=True))
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )
    return updated_user

'''
@user_router.put("/avatar")
async def upload_user_avatar(
        file: UploadFile = File(...),
        current_user: Annotated[UserResponse, Depends(get_current_user)],
        repo: Annotated[UserRepository, Depends(get_user_repo)],
        s3_repo: Annotated[S3Repository, Depends()]
):
    """Загрузка аватара пользователя"""
    await validate_file(file)
    file_ext = file.filename.split(".")[-1]
    object_name = f"avatars/{current_user.id}_{datetime.now().timestamp()}.{file_ext}"

    await s3_repo.upload_file(
        bucket="user-photos",
        object_name=object_name,
        file_data=file.file,
        content_type=file.content_type,
    )

    await repo.update_user_info(
        current_user.id, {"avatar_url": object_name}
    )

    avatar_url = await s3_repo.get_file_url("user-photos", object_name)
    return {"message": "Аватар успешно загружен", "avatar_url": avatar_url}
'''