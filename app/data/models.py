from app.data.database import Base
from sqlalchemy import Boolean, Column, Integer, String


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    name = Column(String, nullable=True)
    surname = Column(String, nullable=True)
    avatar_url = Column(
        String, nullable=True
    )  # Путь к фото в MinIO (формат: 'photos/avatars/{user_id}.png')


