import logging
from typing import List, Optional

from fastapi import HTTPException
from passlib.context import CryptContext
from pydantic import EmailStr
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from starlette import status

from app.data.models import User
from app.data.schemas import UserCreate

# Настройка логгера
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # --- Create Operations ---
    async def create_user(self, user_data: UserCreate) -> User:
        """Создание нового пользователя.
        Args:
            user_data: Данные пользователя в формате Pydantic UserCreate.
        Returns:
            User: Созданный пользователь.
        Raises:
            HTTPException: Если создание пользователя не удалось.
        """
        try:
            # Преобразуем Pydantic-модель в словарь
            user_dict = user_data.dict()
            # Хешируем пароль и заменяем 'password' на 'hashed_password'
            user_dict["hashed_password"] = pwd_context.hash(user_dict.pop("password"))

            # Создаем объект User с исправленным словарем
            user = User(**user_dict)
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)
            return user
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Failed to create user: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to create user: {str(e)}"
            )

    # --- Read Operations ---
    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        try:
            result = await self.db.execute(select(User).where(User.id == user_id))
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"Failed to get user by id {user_id}: {str(e)}")
            return None

    async def get_user_by_email(self, email: EmailStr) -> Optional[User]:
        """Получение пользователя по email."""
        try:
            result = await self.db.execute(select(User).where(User.email == email))
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"Failed to get user by email {email}: {str(e)}")
            return None

    async def get_all_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        """Получение списка пользователей с пагинацией."""
        try:
            result = await self.db.execute(select(User).offset(skip).limit(limit))
            return result.scalars().all()
        except SQLAlchemyError as e:
            logger.error(f"Failed to get all users: {str(e)}")
            return []

    # --- Update Operations ---
    async def update_user_info(self, user_id: int, update_data: dict) -> Optional[User]:
        """Общее обновление информации о пользователе."""
        try:
            result = await self.db.execute(
                update(User)
                .where(User.id == user_id)
                .values(**update_data)
                .execution_options(synchronize_session="fetch")  # Синхронизация сессии
                .returning(User)
            )
            user = result.scalar_one_or_none()
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            await self.db.commit()
            return user
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"User update failed for id {user_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to update user: {str(e)}"
            )

    async def update_user_password(self, user_id: int, hashed_password: str) -> None:
        """Обновление пароля пользователя."""
        try:
            result = await self.db.execute(
                update(User)
                .where(User.id == user_id)
                .values(hashed_password=hashed_password)
            )
            if result.rowcount == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            await self.db.commit()
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Password update failed for id {user_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to update password: {str(e)}"
            )

    # --- Delete Operations ---
    async def delete_user(self, user_id: int) -> None:
        """Удаление пользователя."""
        try:
            result = await self.db.execute(delete(User).where(User.id == user_id))
            if result.rowcount == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            await self.db.commit()
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"User deletion failed for id {user_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to delete user: {str(e)}"
            )

    # --- Verification Methods ---
    async def verify_user_exists(self, email: EmailStr) -> bool:
        """Проверка существования пользователя."""
        try:
            result = await self.db.execute(
                select(User).where(User.email == email).exists().select()
            )
            return result.scalar()
        except SQLAlchemyError as e:
            logger.error(f"Failed to verify user existence for email {email}: {str(e)}")
            return False

    # --- Utility Methods ---
    async def count_active_users(self) -> int:
        """Получение количества активных пользователей."""
        try:
            result = await self.db.execute(
                select(User).where(User.is_active == True)  # Предполагается наличие is_active
            )
            return len(result.scalars().all())
        except SQLAlchemyError as e:
            logger.error(f"Failed to count active users: {str(e)}")
            return 0