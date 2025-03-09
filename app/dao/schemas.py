from pydantic import BaseModel, EmailStr, constr

class UserCreate(BaseModel):
    email: EmailStr
    username: constr(min_length=3, max_length=30)
    phone: constr(regex=r'^\+?[1-9]\d{1,14}$')  # Проверка формата телефона
    profile_picture: str = None  # Можно сделать необязательным
    password: constr(min_length=6)

class User(BaseModel):
    id: int
    email: EmailStr
    username: str
    phone: str
    profile_picture: str = None
