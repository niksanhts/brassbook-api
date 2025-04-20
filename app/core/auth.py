import logging
from fastapi import Depends, HTTPException, Request, status
from jose import ExpiredSignatureError, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from authx import AuthX, AuthXConfig
from app.config import JWT_ACCESS_COOKIE_NAME, JWT_REFRESH_COOKIE_NAME, JWT_SECRET_KEY
from app.data.database import get_db
from app.data.models import User
from app.data.schemas import AuthResponse, Login, Register

# Configure logging
logger = logging.getLogger(__name__)

# Configure AuthX
config = AuthXConfig()
config.JWT_SECRET_KEY = JWT_SECRET_KEY
config.JWT_ACCESS_COOKIE_NAME = JWT_ACCESS_COOKIE_NAME
config.JWT_REFRESH_COOKIE_NAME = JWT_REFRESH_COOKIE_NAME
config.JWT_TOKEN_LOCATION = ["cookies", "headers"]

security = AuthX(config=config)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def register(data: Register, db: Session) -> AuthResponse:
    """
    Register a new user and generate access and refresh tokens.

    Args:
        data: Registration data (email, password).
        db: SQLAlchemy database session.

    Returns:
        AuthResponse: Access and refresh tokens.

    Raises:
        HTTPException: If email is already registered or registration fails.
    """
    logger.info("Registering user: %s", data.email)
    existing_user = db.query(User).filter(User.email == data.email).first()
    if existing_user:
        logger.warning("Email already registered: %s", data.email)
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = pwd_context.hash(data.password)
    user = User(email=data.email, hashed_password=hashed_password, status="active") 
    # TODO для начала пользователь активируется автоматитчески. Потом добавим проверку

    try:
        db.add(user)
        db.commit()
        db.refresh(user)
        access_token = security.create_access_token(uid=str(user.id))
        refresh_token = security.create_refresh_token(uid=str(user.id))
        logger.info("User registered successfully: %s", data.email)
        return AuthResponse(access_token=access_token, refresh_token=refresh_token)
    except Exception as e:
        logger.error("Failed to register user %s: %s", data.email, str(e))
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to register user")


def login(data: Login, db: Session) -> AuthResponse:
    """
    Log in a user and generate access and refresh tokens.

    Args:
        data: Login data (email, password).
        db: SQLAlchemy database session.

    Returns:
        AuthResponse: Access and refresh tokens.

    Raises:
        HTTPException: If credentials are invalid or user is not active.
    """
    logger.info("Login attempt for user: %s", data.email)
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        logger.warning("User not found: %s", data.email)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    
    if not pwd_context.verify(data.password, user.hashed_password):
        logger.warning("Invalid password for user: %s", data.email)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    
    if user.status != "active":
        logger.warning("User account not active: %s", data.email)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account not activated")

    try:
        access_token = security.create_access_token(uid=str(user.id))
        refresh_token = security.create_refresh_token(uid=str(user.id))
        logger.info("User logged in successfully: %s", data.email)
        return AuthResponse(access_token=access_token, refresh_token=refresh_token)
    except Exception as e:
        logger.error("Failed to generate tokens for %s: %s", data.email, str(e))
        raise HTTPException(status_code=500, detail="Failed to log in")


def check_token(access_token: str) -> bool:
    """
    Check if the provided access token is valid.

    Args:
        access_token: JWT access token.

    Returns:
        bool: True if token is valid, False otherwise.

    Raises:
        HTTPException: If token is invalid, expired, or an error occurs.
    """
    logger.debug("Checking token validity")
    try:
        payload = security._decode_token(access_token)
        # TODO нормально проверять TokenPayload
        security.verify_token(access_token)
        if not payload or "uid" not in payload:
            logger.warning("Invalid token payload")
            raise HTTPException(status_code=403, detail="Invalid token")
        logger.info("Token is valid")
        return True
    except ExpiredSignatureError:
        logger.warning("Token has expired")
        raise HTTPException(status_code=403, detail="Token has expired")
    except JWTError as e:
        logger.warning("Invalid token: %s", str(e))
        raise HTTPException(status_code=403, detail="Invalid token signature or structure")
    except Exception as e:
        logger.error("Unexpected error while decoding token: %s", str(e))
        raise HTTPException(status_code=500, detail="Internal error while decoding token")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """
    Retrieve the current authenticated user from the access token.

    Args:
        request: FastAPI request object containing cookies or headers.
        db: SQLAlchemy database session.

    Returns:
        User: Authenticated user object.

    Raises:
        HTTPException: If token is missing, invalid, or user is not found.
    """
    logger.debug("Retrieving current user")
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]  # Remove "Bearer " prefix
        logger.debug("Token found in Authorization header")
    else:
        token = request.cookies.get(JWT_ACCESS_COOKIE_NAME)
        logger.debug("Token found in cookie: %s", JWT_ACCESS_COOKIE_NAME)

    if not token:
        logger.warning("No token provided")
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = security._decode_token(token)
        # TODO нормально проверять TokenPayload
        user_id_str = payload.sub
        if not user_id_str:
            logger.warning("Invalid token: missing user ID")
            raise HTTPException(status_code=401, detail="Invalid token")

        try:
            user_id = int(user_id_str)
        except ValueError:
            logger.warning("Invalid user ID format: %s", user_id_str)
            raise HTTPException(status_code=401, detail="Invalid token")

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.warning("User not found for ID: %s", user_id)
            raise HTTPException(status_code=401, detail="User not found")

        logger.info("User authenticated: %s", user.email)
        return user
    except ExpiredSignatureError:
        logger.warning("Token has expired")
        raise HTTPException(status_code=401, detail="Token has expired")
    except JWTError as e:
        logger.warning("Invalid token: %s", str(e))
        raise HTTPException(status_code=401, detail="Invalid or malformed token")
    except Exception as e:
        logger.error("Unexpected error while authenticating user: %s", str(e))
        raise HTTPException(status_code=500, detail="Internal server error")