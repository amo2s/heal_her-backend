import asyncio
import inspect
import logging
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import redis.asyncio as redis
from passlib.context import CryptContext

# Adjust these imports based on your exact file structure
from auth.models.signup import User 
from auth.login.schemas.login import LoginValidationSchema, LoginResponse, UserType

# 1. Import your central settings
from core.config import settings
from core.security import create_access_token, create_refresh_token

# [UPDATE]: Central Security Shield exceptions.
from core.exceptions import AuthenticationError, InfrastructureError

# Set up professional security logging
logger = logging.getLogger("HEAL_SECURITY")
logger.setLevel(logging.WARNING)

# ---------------------------------------------------------
# THE ENUMERATED ROUTING WARDEN (Advanced Mapping)
# ---------------------------------------------------------
class SecurityRole(str, Enum):
    """
    Strict Bounded Context for System Roles.
    Guarantees perfect synchronization between database security layers and Next.js frontend paths.
    """
    KID = "kid"
    TEEN = "teen"
    YOUNG_ADULT = "young_adult"

    @property
    def dashboard_route(self) -> str:
        """O(1) Route Resolution to strictly pluralize the frontend path."""
        _routing_table = {
            self.KID: "kids",
            self.TEEN: "teens",
            self.YOUNG_ADULT: "young-adults"
        }
        return _routing_table[self]

    @classmethod
    def safe_resolve(cls, raw_role: str) -> "SecurityRole":
        """
        Safely casts a raw database string to a strict SecurityRole.
        Prevents 500 crashes if a legacy user has an invalid role.
        """
        try:
            return cls(raw_role)
        except ValueError:
            logger.error(f"DATA INTEGRITY WARNING: Invalid role '{raw_role}' found. Defaulting to safe young_adult path.")
            return cls.YOUNG_ADULT


# ---------------------------------------------------------
# SECURITY CONFIGURATION
# ---------------------------------------------------------
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

# Use settings instead of os.getenv
valkey_client = redis.from_url(settings.REDIS_URL, decode_responses=True)


# ---------------------------------------------------------
# THE SERVICE LOGIC
# ---------------------------------------------------------
async def execute_login(
    credentials: LoginValidationSchema, 
    client_ip: str, 
    db # We let the adaptive engine handle the typing
) -> LoginResponse:
    
    # 1. FETCH GHOST HASH directly from settings
    dummy_hash = settings.DUMMY_PASSWORD_HASH
    if not dummy_hash:
        raise InfrastructureError(
            internal_message="CRITICAL MISCONFIGURATION: DUMMY_PASSWORD_HASH missing from environment."
        )

    # 2. ADAPTIVE DATABASE QUERY
    query = select(User).where(User.email == credentials.email)
    execute_result = db.execute(query)
    
    if inspect.isawaitable(execute_result):
        result = await execute_result
    else:
        result = execute_result
        
    user = result.scalars().first()

    # ---------------------------------------------------------
    # 3. THE GHOST PROTOCOL (Timing Attack & Format Shield)
    # ---------------------------------------------------------
    is_valid_password = False
    
    # [UPDATE]: Defensive Wrapper prevents Passlib from crashing the server
    # if the DB hash or .env dummy_hash is structurally malformed.
    try:
        if user:
            is_valid_password = await asyncio.to_thread(
                pwd_context.verify, credentials.password, user.password_hash
            )
        else:
            await asyncio.to_thread(
                pwd_context.verify, credentials.password, dummy_hash
            )
            is_valid_password = False
            
    except ValueError as e:
        # Catch passlib's MalformedHashError silently.
        logger.error(f"[SECURITY SHIELD] Hash Verification Error (Malformed DB or ENV string): {str(e)}")
        is_valid_password = False

    # ---------------------------------------------------------
    # 4. THE DUAL-AXIS STRIKE SYSTEM (Valkey)
    # ---------------------------------------------------------
    if not user or not is_valid_password:
        try:
            ip_key = f"login_fails_ip:{client_ip}"
            email_key = f"login_fails_email:{credentials.email}"

            ip_strikes = await valkey_client.incr(ip_key)
            email_strikes = await valkey_client.incr(email_key)

            if ip_strikes == 1:
                await valkey_client.expire(ip_key, 900)
            if email_strikes == 1:
                await valkey_client.expire(email_key, 900)
        except redis.RedisError as e:
            logger.error(f"[INFRASTRUCTURE SHIELD] Valkey connection failed during strike increment: {str(e)}")

        raise AuthenticationError(
            internal_message=f"Failed login attempt for {credentials.email} from IP {client_ip}"
        )

    # ---------------------------------------------------------
    # 5. THE FORGIVENESS PROTOCOL
    # ---------------------------------------------------------
    try:
        await valkey_client.delete(f"login_fails_ip:{client_ip}")
        await valkey_client.delete(f"login_fails_email:{credentials.email}")
    except redis.RedisError as e:
        logger.error(f"[INFRASTRUCTURE SHIELD] Valkey connection failed during forgiveness protocol: {str(e)}")

    # 5.5 ADVANCED ROLE RESOLUTION
    raw_user_role = getattr(user, 'role', 'young_adult') 
    security_role = SecurityRole.safe_resolve(raw_user_role)

    secure_role_string = security_role.value          
    frontend_dashboard_path = security_role.dashboard_route 

    # ---------------------------------------------------------
    # 6. GENERATE THE VAULT KEYS (The Centralized Upgrade)
    # ---------------------------------------------------------
    token_payload = {
        "sub": str(user.id),
        "role": secure_role_string,        
        "dashboard": frontend_dashboard_path
    }

    access_token = create_access_token(data=token_payload, domain=secure_role_string)
    refresh_token = create_refresh_token(data=token_payload, domain=secure_role_string)

    # ---------------------------------------------------------
    # 7. PACKAGE THE SAFE RESPONSE
    # ---------------------------------------------------------
    safe_user = UserType(
        id=str(user.id),
        email=user.email,
        full_name=getattr(user, 'full_name', getattr(user, 'fullName', 'User')), 
        is_active=getattr(user, 'is_active', True),
        dashboard=frontend_dashboard_path  
    )

    logger.info(f"Login Success: {user.email} | DB Role: {secure_role_string} | Routing: /{frontend_dashboard_path}")

    return LoginResponse(
        status="success",
        message="Authentication successful.",
        access_token=access_token,
        refresh_token=refresh_token,
        user=safe_user
    )