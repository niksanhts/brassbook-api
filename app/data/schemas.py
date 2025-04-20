from typing import Optional

from pydantic import BaseModel, EmailStr


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str


class Register(BaseModel):
    email: EmailStr
    password: str


class Login(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    name: str
    surname: str
    avatar_url: Optional[str] = None

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    surname: Optional[str] = None

