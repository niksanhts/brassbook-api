import logging
import asyncio

from fastapi import APIRouter, File, UploadFile, Depends, HTTPException

from .core.compare_melodies import compare_melodies
from .core.auth import register, login, oauth2_scheme, users_db
from .data.models import User
from .data.file_handler import save_profile_picture

router = APIRouter(prefix="/api")
auth_router = APIRouter(tags=["auth"], prefix="/auth")
compare_router = APIRouter(tags=["compare"], prefix="/compare")
user_router = APIRouter(tags=["users"], prefix="/users")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(threadName)s - %(levelname)s - %(message)s')    


@compare_router.post("/compare_melodies/")
async def compare_melodies_endpoint(
    file1: UploadFile = File(...), file2: UploadFile = File(...)
):
    logging.info("Начало сравнения мелодий")
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
        logging.error("Ошибка в функции %s: %s", __name__, str(e))
        return {"error": str(e)}

@auth_router.post("/login")
async def login_endpoint(token_data = Depends(login)):
    return token_data

@auth_router.post("/register")
async def register_endpoint(username: str, password: str):
    return register(username, password)


outer = APIRouter()


@user_router.put("/users/{username}", response_model=User)
async def update_user(username: str, user_data: User, file: UploadFile = File(None),
                      token: str = Depends(oauth2_scheme)):
    user = users_db.get(username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Обновляем информацию о пользователе
    user["full_name"] = user_data.full_name
    user["email"] = user_data.email

    # Если файл был загружен, сохраняем его
    if file:
        profile_picture_path = await save_profile_picture(file)
        user["profile_picture"] = profile_picture_path

    return user

router.include_router(user_router)
router.include_router(auth_router)
router.include_router(compare_router)