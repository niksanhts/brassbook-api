import logging
import random
from datetime import datetime
from typing import Optional

from jsonschema import ValidationError

from authx import RequestToken
from fastapi import APIRouter, Body, Depends, File, Response, UploadFile, HTTPException, Request, Cookie
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
import jwt

from app.config import JWT_REFRESH_COOKIE_NAME, MINIO_BUCKET_NAME, MAX_FILE_SIZE
from app.core.auth import get_current_user, pwd_context, security
from app.core.email_sender import send_verification_email
from app.data.database import get_db
from app.data.models import User
from app.data.storage import get_minio_client

# Configure logging
logger = logging.getLogger(__name__)

minio_client = get_minio_client()

router = APIRouter(prefix="/api/v1", tags=["legacy"])

class Register(BaseModel):
    role_name: str
    email: EmailStr
    password: str


class VerifyUser(BaseModel):
    email: EmailStr
    code: str


class SendCode(BaseModel):
    email: EmailStr


class Login(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str


class UpdateUser(BaseModel):
    first_name: Optional[str] = None
    second_name: Optional[str] = None
    email: Optional[EmailStr] = None


class PasswordUpdate(BaseModel):
    current_password: str
    new_password: str

def register(data: Register, db: Session) -> dict:
    """
    Register a new user and send a verification email.

    Args:
        data: Registration data (email, password).
        db: SQLAlchemy database session.

    Returns:
        dict: User ID.

    Raises:
        HTTPException: If email is already registered.
    """
    logger.info("Registering user: %s", data.email)
    existing_user = db.query(User).filter(User.email == data.email).first()
    if existing_user:
        logger.warning("Email already registered: %s", data.email)
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = pwd_context.hash(data.password)
    code = 100 # TODO: Заменть на нормальное создание кода
    code_date = datetime.utcnow()
    user = User(
        email=data.email,
        hashed_password=hashed_password,
        code=code,
        code_date=code_date,
        status="active", # "active" | "pending"
    )
    try:
        db.add(user)
        db.commit()
        db.refresh(user)
        send_verification_email(user.email, code) # TODO сделать чтобы работало
        logger.info("User registered successfully: %s", data.email)
        return {"id": user.id}
    except Exception as e:
        logger.error("Failed to register user %s: %s", data.email, str(e))
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to register user")


def verify_user(data: VerifyUser, db: Session) -> dict:
    """
    Verify a user with the provided email and code.

    Args:
        data: Verification data (email, code).
        db: SQLAlchemy database session.

    Returns:
        dict: Success message.

    Raises:
        HTTPException: If user not found, code expired, or invalid code.
    """
    logger.info("Verifying user: %s", data.email)
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        logger.warning("User not found: %s", data.email)
        raise HTTPException(status_code=404, detail="User not found")
    #if (datetime.utcnow() - user.code_date).total_seconds() > 15 * 60:
     #   logger.warning("Verification code expired for user: %s", data.email)
      #  raise HTTPException(status_code=400, detail="Code expired")
    #if str(user.code) == data.code:
    user.status = "active"
    db.commit()
    logger.info("User verified successfully: %s", data.email)
    return {"message": "User activated"}
    #logger.warning("Invalid verification code for user: %s", data.email)
    #raise HTTPException(status_code=400, detail="Invalid code")


def send_code(data: SendCode, db: Session) -> dict:
    """
    Send a verification code to the user's email.

    Args:
        data: Email data.
        db: SQLAlchemy database session.

    Returns:
        dict: Success message.

    Raises:
        HTTPException: If user not found.
    """
    logger.info("Sending verification code to: %s", data.email)
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        logger.warning("User not found: %s", data.email)
        raise HTTPException(status_code=404, detail="User not found")
    code = random.randint(100000, 999999)
    user.code = code
    user.code_date = datetime.utcnow()
    try:
        db.commit()
        send_verification_email(user.email, code)
        logger.info("Verification code sent to: %s", data.email)
        return {"message": "Code sent"}
    except Exception as e:
        logger.error("Failed to send code to %s: %s", data.email, str(e))
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to send code")


def login(data: Login, db: Session) -> AuthResponse:
    """
    Log in a user and generate access and refresh tokens.

    Args:
        data: Login data (email, password).
        db: SQLAlchemy database session.

    Returns:
        AuthResponse: Access and refresh tokens.

    Raises:
        HTTPException: If credentials are invalid.
    """
    logger.info("Login attempt for user: %s", data.email)
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not pwd_context.verify(data.password, user.hashed_password):
        logger.warning("Invalid credentials for user: %s", data.email)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access_token = security.create_access_token(uid=str(user.id))
    refresh_token = security.create_refresh_token(uid=str(user.id))
    logger.info("User logged in successfully: %s", data.email)
    return AuthResponse(access_token=access_token, refresh_token=refresh_token)


def check_token(access_token: str, db: Session) -> User:
    """
    Check if the provided access token is valid.

    Args:
        access_token: JWT access token.
        db: SQLAlchemy database session.

    Returns:
        User: User object if token is valid.

    Raises:
        HTTPException: If token is invalid or user not found.
    """
    logger.debug("Checking token validity")
    try:
        payload = security._decode_token(access_token)
        user_id = payload.sub
        user = db.query(User).filter(User.id == user_id).first()
        if user and payload.time_until_expiry.total_seconds() > 0:
            logger.info("Token valid for user ID: %s", user_id)
            return user
        logger.warning("User not found for ID: %s", user_id)
        raise HTTPException(status_code=404, detail="User not found")
    except Exception as e:
        logger.error("Invalid or expired token: %s", str(e))
        raise HTTPException(status_code=403, detail="Invalid or expired token")


def refresh_token(request: Request, db: Session) -> JSONResponse:
    """
    Refresh the access token using the refresh token.

    Args:
        request: FastAPI request object.
        db: SQLAlchemy database session.

    Returns:
        JSONResponse: New access token and updated refresh token cookie.

    Raises:
        HTTPException: If refresh token is missing, invalid, or user not found.
    """
    logger.debug("Refreshing token")
    refresh_token = request.cookies.get(JWT_REFRESH_COOKIE_NAME)
    if not refresh_token:
        logger.warning("Refresh token not found")
        raise HTTPException(status_code=400, detail="Refresh token not found")
    try:
        payload = security.decode_token(refresh_token)
        user_id = payload.get("uid")
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.warning("User not found for ID: %s", user_id)
            raise HTTPException(status_code=404, detail="User not found")
        new_access_token = security.create_access_token(uid=str(user.id))
        new_refresh_token = security.create_refresh_token(uid=str(user.id))
        response = JSONResponse(content={"access_token": new_access_token})
        response.set_cookie(
            key=JWT_REFRESH_COOKIE_NAME,
            value=new_refresh_token,
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=60 * 24 * 60 * 60,  # 60 days
        )
        logger.info("Token refreshed successfully for user ID: %s", user_id)
        return response
    except jwt.PyJWTError as e:
        logger.error("Invalid or expired refresh token: %s", str(e))
        raise HTTPException(status_code=403, detail="Invalid or expired refresh token")


def password_update(current_password: str, new_password: str, user: User, db: Session) -> dict:
    """
    Update the user's password.

    Args:
        current_password: Current password.
        new_password: New password.
        user: Current authenticated user.
        db: SQLAlchemy database session.

    Returns:
        dict: Success message.

    Raises:
        HTTPException: If current password is invalid.
    """
    logger.info("Password update request for user: %s", user.email)
    if not pwd_context.verify(current_password, user.hashed_password):
        logger.warning("Invalid current password for user: %s", user.email)
        raise HTTPException(status_code=400, detail="Invalid current password")
    hashed_new_password = pwd_context.hash(new_password)
    user.hashed_password = hashed_new_password
    try:
        db.commit()
        logger.info("Password updated successfully for user: %s", user.email)
        return {"message": "Password updated"}
    except Exception as e:
        logger.error("Failed to update password for %s: %s", user.email, str(e))
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update password")


def update_user(data: UpdateUser, user: User, db: Session) -> User:
    """
    Update user profile information.

    Args:
        data: Update data (first_name, second_name, email).
        user: Current authenticated user.
        db: SQLAlchemy database session.

    Returns:
        User: Updated user object.

    Raises:
        HTTPException: If email is already taken.
    """
    logger.info("Updating profile for user: %s", user.email)
    if data.email and data.email != user.email:
        existing_user = db.query(User).filter(User.email == data.email).first()
        if existing_user:
            logger.warning("Email already taken: %s", data.email)
            raise HTTPException(status_code=400, detail="Email already taken")
        user.email = data.email
    if data.first_name is not None:
        user.first_name = data.first_name
    if data.second_name is not None:
        user.second_name = data.second_name
    try:
        db.commit()
        logger.info("Profile updated successfully for user: %s", user.email)
        return user
    except Exception as e:
        logger.error("Failed to update profile for %s: %s", user.email, str(e))
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update profile")


def update_avatar(avatar: UploadFile, user: User, db: Session) -> User:
    """
    Update the user's avatar and store it in MinIO.

    Args:
        avatar: Uploaded avatar file.
        user: Current authenticated user.
        db: SQLAlchemy database session.

    Returns:
        User: Updated user object.

    Raises:
        HTTPException: If file is too large or upload fails.
    """
    logger.info("Updating avatar for user: %s, file: %s", user.email, avatar.filename)
    if avatar.size > MAX_FILE_SIZE:
        logger.warning("Avatar file too large: %s", avatar.filename)
        raise HTTPException(status_code=413, detail="File size exceeds limit of 5MB")

    # Sanitize filename to prevent path injection
    safe_filename = avatar.filename.replace("/", "_").replace("\\", "_")
    object_name = f"avatars/{user.id}_{safe_filename}"

    try:
        avatar.file.seek(0, 2)
        file_size = avatar.file.tell()
        avatar.file.seek(0)
        minio_client.put_object(
            bucket_name=MINIO_BUCKET_NAME,
            object_name=object_name,
            data=avatar.file,
            length=file_size,
            content_type=avatar.content_type or "application/octet-stream",
        )
        avatar_url = minio_client.presigned_get_object(MINIO_BUCKET_NAME, object_name)
        user.avatar = avatar_url
        db.commit()
        logger.info("Avatar updated successfully for user: %s", user.email)
        return user
    except Exception as e:
        logger.error("Failed to update avatar for %s: %s", user.email, str(e))
        raise HTTPException(status_code=500, detail="Failed to upload avatar")


@router.post("/auth/registration", response_model=AuthResponse)
async def register_user(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    content_type = request.headers.get("Content-Type", "")

    logger.info("----[XYI]----")  

    if "application/json" in content_type:
        try:
            data = Register(**await request.json())
        except ValidationError as e:
            return JSONResponse(status_code=422, content={"detail": e.errors()})
    elif "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        try:
            data = Register(
                role_name=form.get("role_name"),
                password=form.get("password"),
                email=form.get("email")
            )
        except ValidationError as e:
            return JSONResponse(status_code=422, content={"detail": e.errors()})
    else:
        return JSONResponse(status_code=415, content={"detail": "Unsupported Media Type"})

    register(data, db)
    result = login(data, db)

    response.set_cookie(key="access_token", value=result.access_token)
    response.set_cookie(key="refresh_token", value=result.refresh_token)

    return result


@router.post("/auth/verifyuser", response_model=dict)
def verify_user_endpoint(data: VerifyUser, db: Session = Depends(get_db)):
    """Verify a user with email and code."""
    return verify_user(data, db)


@router.post("/auth/sendcode", response_model=dict)
def send_code_endpoint(data: SendCode, db: Session = Depends(get_db)):
    """Send a verification code to the user."""
    return send_code(data, db)


from fastapi import Form

@router.post("/auth/login", response_model=AuthResponse)
def login_user(
    response: Response,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    result = login(Login(email=email, password=password), db)

    response.set_cookie(key="access_token", value=result.access_token)
    response.set_cookie(key="refresh_token", value=result.refresh_token)

    return result



from fastapi import HTTPException, status
from typing import Optional

@router.post("/auth/check")
async def check_token_endpoint(
    access_token: Optional[str] = Body(None),
    cookie_token: Optional[str] = Cookie(None, alias="access_token"),
    db: Session = Depends(get_db)
):
    """
    Проверяет валидность токена. Принимает токен:
    - В теле запроса (access_token)
    - В куках (access_token)
    
    Если переданы оба токена, проверяет их оба и возвращает результат
    для первого валидного.
    """
    
    # Собираем все полученные токены (исключая None)
    tokens = [token for token in [access_token, cookie_token] if token is not None]
    
    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Требуется токен: укажите access_token в теле запроса или куках"
        )
    
    # Проверяем токены по порядку
    for token in tokens:
        try:
            result = check_token(token, db)
            # Если токен валиден, возвращаем результат
            return result
        except HTTPException:
            # Пробуем следующий токен
            continue
    
    # Если ни один токен не прошел проверку
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Все предоставленные токены недействительны"
    )


@router.get("/auth/refresh", response_model=dict)
def refresh_token_endpoint(request: Request, db: Session = Depends(get_db)):
    """Refresh the access token."""
    return refresh_token(request, db)


@router.put("/auth/password", response_model=dict, dependencies=[Depends(security.get_token_from_request)])
def update_password(
    data: PasswordUpdate,
    token: RequestToken = Depends(),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update the user's password."""
    try: 
        security.verify_token(token=token)
        return password_update(data.current_password, data.new_password, user, db)
    except Exception as e:
          raise HTTPException(401, detail={"message": str(e)}) from e


@router.put("/auth", dependencies=[Depends(security.get_token_from_request)])
def update_user_endpoint(
    data: UpdateUser,
    token: RequestToken = Depends(),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update the user's profile."""
    try: 
        security.verify_token(token=token)
        return update_user(data, user, db)
    except Exception as e:
          raise HTTPException(401, detail={"message": str(e)}) from e
    


@router.put("/auth/avatar", dependencies=[Depends(security.get_token_from_request)])
def update_avatar_endpoint(
    token: RequestToken = Depends(),
    avatar: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update the user's avatar."""
    try: 
        security.verify_token(token=token)
        return update_avatar(avatar, user, db)
    except Exception as e:
          raise HTTPException(401, detail={"message": str(e)}) from e