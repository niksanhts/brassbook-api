import asyncio
import os
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles  # Добавлено для статических файлов
from jose import jwt, JWTError
from passlib.context import CryptContext
from datetime import datetime, timedelta
from pydantic import BaseModel, EmailStr
from typing import Optional
import shutil
from dotenv import load_dotenv

from app.core.compare_melodies import compare_melodies

# Загрузка переменных окружения
load_dotenv()
app = FastAPI()

# Монтируем папку с аватарами как статическую
app.mount("/api/v1/static", StaticFiles(directory="avatars"), name="static")

# Настройки CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Конфигурация
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = 30


# Модели данных
class User(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    disabled: Optional[bool] = False


class UserInDB(User):
    hashed_password: str
    avatar: Optional[str] = None


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[EmailStr] = None


class UserUpdate(BaseModel):
    full_name: Optional[str] = None


class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None


# "База данных" (ключ - email)
fake_users_db = {
    "fake_user@example.com": {
        "email": "fake_user@example.com",
        "full_name": "John Doe",
        "hashed_password": "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",
        "disabled": False,
        "avatar": None
    }
}

# Утилиты
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/token")


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def get_user(db, email: str):
    if email in db:
        user_dict = db[email]
        return UserInDB(**user_dict)


def authenticate_user(fake_db, email: str, password: str):
    user = get_user(fake_db, email)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception
    user = get_user(fake_users_db, email=token_data.email)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


# Папка для загрузки аватаров
AVATAR_DIR = "avatars"
os.makedirs(AVATAR_DIR, exist_ok=True)


# Роуты с префиксом /api/v1
@app.post("/api/v1/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(fake_users_db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/api/v1/register")
async def register(user_data: UserRegister):
    if user_data.email in fake_users_db:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = get_password_hash(user_data.password)
    fake_users_db[user_data.email] = {
        "email": user_data.email,
        "full_name": user_data.full_name,
        "hashed_password": hashed_password,
        "disabled": False,
        "avatar": None
    }
    return {"message": "User created successfully"}


@app.get("/api/v1/users/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user


@app.put("/api/v1/users/me")
async def update_user_profile(
        user_update: UserUpdate,
        current_user: User = Depends(get_current_active_user)
):
    user_data = fake_users_db[current_user.email]
    if user_update.full_name is not None:
        user_data["full_name"] = user_update.full_name

    return {"message": "Profile updated successfully"}


@app.post("/api/v1/users/me/avatar")
async def upload_avatar(
        file: UploadFile = File(...),
        current_user: User = Depends(get_current_active_user)
):
    # Генерируем уникальное имя файла
    file_ext = os.path.splitext(file.filename)[1]
    filename = f"{current_user.email.replace('@', '_').replace('.', '_')}{file_ext}"
    file_location = f"{AVATAR_DIR}/{filename}"

    # Сохраняем файл
    with open(file_location, "wb+") as file_object:
        shutil.copyfileobj(file.file, file_object)

    # Обновляем путь к аватару в "БД"
    fake_users_db[current_user.email]["avatar"] = f"/api/v1/static/{filename}"

    return {"avatar_url": fake_users_db[current_user.email]["avatar"]}

@app.get("/api/v1/users/me/avatar")
async def get_avatar(current_user: User = Depends(get_current_active_user)):
    avatar_path = fake_users_db[current_user.email]["avatar"]
    if not avatar_path:
        raise HTTPException(status_code=404, detail="Avatar not found")
    return {"avatar_url": avatar_path}

@app.post("/api/v1/compare_melodies/")
async def compare_melodies_endpoint(
    file1: UploadFile = File(...),
    file2: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user)
):
    try:
        file1_content = await file1.read()
        file2_content = await file2.read()

        result = await asyncio.to_thread(
            compare_melodies,
            file1_content,
            file2_content
        )

        if result is None:
            return {"error": "Ошибка при сравнении мелодий"}

        return {"result": result}

    except Exception as e:
        return {"error": str(e)}
