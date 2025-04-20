from fastapi import APIRouter, Depends
from app.core.auth import get_current_user, pwd_context, security
from pydantic import BaseModel
from sqlalchemy import String
from sqlalchemy.orm import Session
from app.core.auth import get_current_user
from app.data.database import get_db
from app.data.models import User
from authx import RequestToken



current_user_router = APIRouter(prefix="/v2/users/me", tags=["user"])


class UserResponse(BaseModel):
    email: str
    id: int
    first_name: str
    second_name: str

@current_user_router.get("/", dependencies=[Depends(security.get_token_from_request)])
async def read_current_user(
    token: RequestToken = Depends(),
    user: User = Depends(get_current_user),
) -> UserResponse:
    return UserResponse(email = "" if user.email is None else user.email, 
                        id = "" if user.id is None else user.id , 
                        first_name="" if user.first_name is None else user.first_name , 
                        second_name="" if user.second_name is None else user.second_name )


@current_user_router.put("/")
async def update_user_info(): ...


@current_user_router.put("/password")
async def update_user_password(): ...


avatar_user_router = APIRouter(prefix="/v2/users/avatar", tags=["avatar"])


class AvatarUrl(BaseModel):
    url: str
@avatar_user_router.get("/", dependencies=[Depends(security.get_token_from_request)], response_model=AvatarUrl)
async def get_user_avatar(
    user: User = Depends(get_current_user),
    token: RequestToken = Depends()
) -> AvatarUrl:
    return AvatarUrl(url = "" if user.photo_url is None else user.photo_url)

@avatar_user_router.put("/", dependencies=[Depends(security.get_token_from_request)])
async def upload_user_avatar(
    req: AvatarUrl,
    token: RequestToken = Depends(),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),

    
):
    user.photo_url = req.url
    try:
        db.commit()
    except:
        db.rollback()
    
    


@avatar_user_router.delete("/", dependencies=[Depends(security.get_token_from_request)])
async def delete_user_avatar(
    token: RequestToken = Depends(),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user.photo_url = None
    try:
        db.commit()
    except:
        db.rollback()