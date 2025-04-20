from fastapi import APIRouter

current_user_router = APIRouter(prefix="/v2/users/me", tags=["user"])


@current_user_router.get("/")
async def read_current_user(): ...


@current_user_router.put("/")
async def update_user_info(): ...


@current_user_router.put("/password")
async def update_user_password(): ...


avatar_user_router = APIRouter(prefix="/v2/users/avatar", tags=["avatar"])


@avatar_user_router.get("/")
async def get_user_avatar(): ...


@avatar_user_router.post("/")
async def upload_user_avatar(): ...


@avatar_user_router.delete("/")
async def delete_user_avatar(): ...
