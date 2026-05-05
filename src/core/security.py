import jwt
from datetime import datetime, timedelta, timezone
from core.config import settings

def create_access_token(data: dict):
    """Generates a short-lived 15-minute access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.ALGORITHM)

def create_refresh_token(data: dict):
    """Generates a long-lived 7-day refresh token."""
    to_encode = data.copy()
    refresh_days = getattr(settings, 'REFRESH_TOKEN_EXPIRE_DAYS', 7)
    expire = datetime.now(timezone.utc) + timedelta(days=refresh_days)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.ALGORITHM)

def verify_refresh_token(token: str):
    """Verifies the 7-day token and ensures it's actually a 'refresh' type."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "refresh":
            raise ValueError("Not a valid refresh token")
        return payload
    except jwt.PyJWTError:
        return None