import logging
import strawberry
from strawberry.types import Info

# [UPDATE]: Simplified Imports. 
# We no longer need GraphQLError or Pydantic's ValidationError here 
# because the Security Shield handles the bubble-up.
from auth.signup.schemas.signup import SignupInputSchema
from auth.signup.services.signup import create_secure_user
from auth.guards import SignupFortressGuard

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
    EXTREMIST SIGNUP HANDLER (SKINNY VERSION)
    The final bridge between the GraphQL endpoint and the Database Service.
    Now 100% "Fail-Safe" via Global Exception Interception.
    """
    
    @strawberry.mutation(permission_classes=[SignupFortressGuard])
    async def signup(
        self,
        info: Info,
        email: str,
        password: str,
        full_name: str,
        age: int,
        bot_trap: str | None = None
    ) -> SignupResponse:
        
        # [UPDATE]: No more manual logging or try/except blocks.
        # If any of the steps below fail, the Security Shield catches it 
        # at the top level, logs the IP/Reason, and returns a safe error.

        # 1. THE PYDANTIC FIREWALL
        # Instantly cast all raw GraphQL strings into our extremely strict schema.
        # This triggers internal validators (Uppercase, Symbols, Age, etc.)
        clean_data = SignupInputSchema(
            email=email,
            password=password,
            full_name=full_name,
            age=age,
            bot_trap=bot_trap
        )

        # 2. EXECUTE THE SERVICE
        # Pass the flawless, sanitized data into the isolated service layer.
        # Service layer now raises 'InfrastructureError' or 'ValidationError' on its own.
        result = await create_secure_user(
            email=clean_data.email,
            full_name=clean_data.full_name,
            plain_password=clean_data.password,
            age=clean_data.age
        )
        
        # 3. SECURE SUCCESS RESPONSE
        # Only reached if every security check and DB insert succeeds.
        return SignupResponse(
            status="success",
            message="Account fortified and created successfully.",
            user_id=result["user_id"]
        )