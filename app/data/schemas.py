from typing import Optional
from pydantic import BaseModel, EmailStr

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    name: str
    surname: str
    avatar_url: Optional[str] = None

# Pydantic модели
class UserCreate(BaseModel):
    email: EmailStr
    password: str
#    name: str
#    surname: str


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    surname: Optional[str] = None


class PasswordUpdate(BaseModel):
    current_password: str
    new_password: str