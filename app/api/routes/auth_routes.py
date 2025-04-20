import logging
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from jose import JWTError, ExpiredSignatureError

from app.config import JWT_ACCESS_COOKIE_NAME, JWT_REFRESH_COOKIE_NAME
from app.core.auth import check_token, login, register, security
from app.data.database import get_db
from app.data.models import User
from app.data.schemas import AuthResponse, Login, Register

# Configure logging
logger = logging.getLogger(__name__)

auth_router = APIRouter(prefix="/v2/auth", tags=["auth"])


@auth_router.post("/register", response_model=AuthResponse)
async def register_endpoint(
    response: Response, request: Register, db: Session = Depends(get_db)
) -> AuthResponse:
    """
    Register a new user and set authentication cookies.

    Args:
        response: FastAPI Response object to set cookies.
        request: Register schema containing user registration data.
        db: SQLAlchemy database session.

    Returns:
        AuthResponse: Authentication response with access and refresh tokens.

    Raises:
        HTTPException: If registration fails due to invalid data or server error.
    """
    logger.info("Received registration request for user: %s", request.email)
    try:
        result = register(request, db)
        response.set_cookie(
            key="access_token",
            value=result.access_token,
            httponly=True,
            secure=True,
            samesite="strict",
        )
        response.set_cookie(
            key="refresh_token",
            value=result.refresh_token,
            httponly=True,
            secure=True,
            samesite="strict",
        )
        logger.info("User %s registered successfully", request.email)
        return result
    except HTTPException as e:
        logger.warning("Registration failed for %s: %s", request.email, str(e))
        raise
    except Exception as e:
        logger.error("Unexpected error during registration for %s: %s", request.email, str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@auth_router.post("/login", response_model=AuthResponse)
async def login_endpoint(
    response: Response, request: Login, db: Session = Depends(get_db)
) -> AuthResponse:
    """
    Log in a user and set authentication cookies.

    Args:
        response: FastAPI Response object to set cookies.
        request: Login schema containing user credentials.
        db: SQLAlchemy database session.

    Returns:
        AuthResponse: Authentication response with access and refresh tokens.

    Raises:
        HTTPException: If login fails due to invalid credentials or server error.
    """
    logger.info("Received login request for user: %s", request.email)
    try:
        result = login(request, db)
        response.set_cookie(
            key="access_token",
            value=result.access_token,
            httponly=True,
            secure=True,
            samesite="strict",
        )
        response.set_cookie(
            key="refresh_token",
            value=result.refresh_token,
            httponly=True,
            secure=True,
            samesite="strict",
        )
        logger.info("User %s logged in successfully", request.email)
        return result
    except HTTPException as e:
        logger.warning("Login failed for %s: %s", request.email, str(e))
        raise
    except Exception as e:
        logger.error("Unexpected error during login for %s: %s", request.email, str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@auth_router.post("/check")
async def check_token_endpoint(request: Request) -> dict:
    """
    Check if the provided access token is valid.

    Args:
        request: FastAPI Request object containing cookies or headers.

    Returns:
        dict: Dictionary with 'valid' key indicating token validity.

    Raises:
        HTTPException: If token is missing or invalid.
    """
    logger.debug("Checking token validity")
    token = request.cookies.get(JWT_ACCESS_COOKIE_NAME) or request.headers.get("Authorization")

    if not token:
        logger.warning("Token not provided in request")
        raise HTTPException(status_code=401, detail="Token not found")

    if token.startswith("Bearer "):
        token = token[7:]

    try:
        is_valid = check_token(token)
        logger.info("Token check result: %s", is_valid)
        return {"valid": is_valid}
    except HTTPException as e:
        logger.warning("Token validation failed: %s", str(e))
        raise
    except Exception as e:
        logger.error("Unexpected error during token validation: %s", str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@auth_router.get("/refresh")
async def refresh_token_endpoint(request: Request, db: Session = Depends(get_db)) -> JSONResponse:
    """
    Refresh the access token using the refresh token.

    Args:
        request: FastAPI Request object containing cookies.
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
        raise HTTPException(status_code=401, detail="Refresh token not found")

    try:
        payload = security.verify_token(refresh_token)
        user_id = payload.get("uid")
        if not user_id:
            logger.warning("Invalid refresh token: missing user ID")
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        user = db.query(User).filter(User.id == int(user_id)).first()
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
        logger.info("Token refreshed successfully for user: %s", user.email)
        return response
    except ExpiredSignatureError:
        logger.warning("Refresh token has expired")
        raise HTTPException(status_code=401, detail="Refresh token has expired")
    except JWTError as e:
        logger.warning("Invalid refresh token: %s", str(e))
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    except Exception as e:
        logger.error("Unexpected error during token refresh: %s", str(e))
        raise HTTPException(status_code=500, detail="Internal server error")