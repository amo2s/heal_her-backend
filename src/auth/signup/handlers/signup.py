import logging
import strawberry
from pydantic import ValidationError
from graphql import GraphQLError
from strawberry.types import Info

# ---------------------------------------------------------
# RELATIVE OR ABSOLUTE IMPORTS
# Ensure these match your exact folder structure
# ---------------------------------------------------------
from auth.signup.schemas.signup import SignupInputSchema
from auth.signup.services.signup import create_secure_user
from auth.guards import SignupFortressGuard

# Initialize an isolated security logger for the auth module
logger = logging.getLogger("auth.signup_handler")
logger.setLevel(logging.INFO)

# --- GRAPHQL RESPONSE SCHEMA ---
@strawberry.type
class SignupResponse:
    """Standardized, safe response object. Never returns raw data."""
    status: str
    message: str
    user_id: str | None = None


@strawberry.type
class SignupHandler:
    """
    EXTREMIST SIGNUP HANDLER
    Acts as the final bridge between the GraphQL endpoint and the Database Service.
    """
    
    @strawberry.mutation(permission_classes=[SignupFortressGuard])
    async def signup(
        self,
        info: Info,
        email: str,
        password: str,
        full_name: str,
        age: int,           # <--- NEW: Age requirement mapped from Frontend
        bot_trap: str | None = None
    ) -> SignupResponse:
        
        # 1. EXTRACT AUDIT CONTEXT
        # Grab the request from the Strawberry Info object to log the attacker/user IP
        request = info.context["request"]
        client_ip = request.client.host

        try:
            # 2. THE PYDANTIC FIREWALL
            # Instantly cast all raw GraphQL strings into our extremely strict schema.
            # If the user tries to inject SQL, massive payloads, or fails regex, it dies right here.
            clean_data = SignupInputSchema(
                email=email,
                password=password,
                full_name=full_name,
                age=age,            # <--- NEW: Passed into Pydantic for validation (ge=5, le=120)
                bot_trap=bot_trap
            )
        except ValidationError as e:
            # 3. SAFE VALIDATION ERROR HANDLING
            # Extract only the safe validation message (e.g., "Password requires uppercase")
            error_msg = e.errors()[0]["msg"]
            logger.warning(f"[VALIDATION FAIL] IP: {client_ip} | Email: {email} | Reason: {error_msg}")
            raise GraphQLError(f"Validation failed: {error_msg}")

        try:
            # 4. EXECUTE THE SERVICE
            # Pass the flawless, sanitized data into the isolated Supabase service layer.
            # Await the execution (non-blocking for FastAPI event loop).
            result = await create_secure_user(
                email=clean_data.email,
                full_name=clean_data.full_name,
                plain_password=clean_data.password,
                age=clean_data.age     # <--- NEW: Passed to service for DB insertion
            )
            
            # 5. SECURE SUCCESS RESPONSE
            logger.info(f"[SIGNUP SUCCESS] IP: {client_ip} | New User ID: {result['user_id']}")
            return SignupResponse(
                status="success",
                message="Account fortified and created successfully.",
                user_id=result["user_id"]
            )

        except ValueError as e:
            # 6. EXPECTED SERVICE REJECTIONS
            # This catches expected errors like our Timing Shield "Email already in use" rejection.
            logger.warning(f"[SIGNUP REJECTED] IP: {client_ip} | Reason: {str(e)}")
            raise GraphQLError(str(e))
            
        except Exception as e:
            # 7. THE ULTIMATE CATCH-ALL (NO STACKTRACE LEAKS)
            # If a massive infrastructure failure occurs (Supabase goes down, Argon2id fails),
            # log the raw traceback internally, but feed the internet a generic failure message.
            logger.error(f"[CRITICAL INFRASTRUCTURE ERROR] IP: {client_ip} | Details: {str(e)}")
            raise GraphQLError("An internal server error occurred. Security team has been notified.")