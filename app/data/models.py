from sqlalchemy import Boolean, Column, DateTime, Integer, String

from app.data.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    code = Column(Integer)
    code_date = Column(DateTime)
    status = Column(String, default="pending")
    first_name = Column(String, nullable=True)
    second_name = Column(String, nullable=True)
    photo_url = Column(
        String, nullable=True
    )  # Путь к фото в MinIO (формат: 'photos/avatars/{user_id}.png')
