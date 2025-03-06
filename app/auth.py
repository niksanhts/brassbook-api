from app.routes import router
from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel
import jwt
import datetime
from typing import Optional
from fastapi.security import OAuth2PasswordBearer
import bcrypt
import os

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

SECRET_KEY = os.getenv("jwt_secret_key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


async def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed_password.decode('utf-8')

async def verify_password(stored_hash: str, password: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))

class User(BaseModel):
    username: str
    password: str 

class RegisterUser(BaseModel):
    username: str
    password: str
    photo: str
    display_name: str
    man: bool


test_users_db = {
    "user1": {
        "username": "user1",
        "password": "password123",
        "photo": "https://avatars.githubusercontent.com/u/2?v=4",
        "display_name" : "user",
        "man": True
    }
}

@router.post("/register")
async def register(user: RegisterUser):
    if user.username in test_users_db:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")
    test_users_db[user.username] = {
        "username": user.username,
        "password": hash_password(user.password),
        "photo": user.photo,
        "display_name": user.display_name,
        "man": user.man
    }
    return {"message": "User successfully registered"}

async def create_access_token(data: dict, expires_delta: Optional[datetime.timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.utcnow() + expires_delta
    else:
        expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

@router.post("/login")
async def login(user: User):
    db_user = test_users_db.get(user.username)
    if db_user is None or not verify_password(db_user["password"], user.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}




@router.get("/user/{username}")
async def get_user(username: str):
    db_user = test_users_db.get(username)
    return {
        "username" : db_user["username"],
        "photo" : db_user["photo"],
        "display_name" : db_user["display_name"],
        "man" : db_user["man"],
    }


async def verify_token(token : str):
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    if int(payload["exp"]) > datetime.datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return payload

@router.get("/protected")
async def protected_route(token: str = Depends(oauth2_scheme)):
    try:
        payload = verify_token(token)
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return {"message": f"Hello {username}, you have access to this protected route!"}
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


@router.post("/set_username")
async def set_username(
    new_username: str,
    token: str = Depends(oauth2_scheme),
):
    try:
        payload = verify_token(token)
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        if username in test_users_db:
            test_users_db[username]["display_name"] = new_username
            return {"message": "Username successfully updated"}
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No such user")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    