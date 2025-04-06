from app.data.database import get_db
from app.data.repositories.users_repository import UserRepository
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

async def get_user_repo(db: AsyncSession = Depends(get_db)):
    return UserRepository(db)