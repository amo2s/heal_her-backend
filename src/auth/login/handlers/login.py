from strawberry.types import Info

# [UPDATE]: Removed GraphQLError and Pydantic ValidationError.
# These are no longer needed here as the Security Shield handles the bubble-up.
from auth.login.schemas.login import LoginInput, LoginResponse
from auth.login.services.login import execute_login

async def handle_login(info: Info, input_data: LoginInput) -> LoginResponse:
    """
    The orchestrator for the login flow. 
    Sits between the GraphQL endpoint and the Service Brain.
    Now 100% "Fail-Safe" via Global Exception Interception.
    """
    
    # 1. EXTRACT CONTEXT
    request = info.context["request"]
    db = info.context["session"]
    
    # --- THE PROXY FIX: EXTRACT REAL IP ---
    # Next.js sends the real user's IP inside this header.
    # We keep this here so we can pass it to the service for rate limiting.
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()
    else:
        client_ip = request.client.host

    # [UPDATE]: Manual try/except blocks removed.
    # If validation or execution fails, the central Security Shield catches it.

    # 2. TRIGGER THE PYDANTIC FIREWALL
    # This now raises ShieldValidationError (aliased) internally.
    clean_credentials = input_data.validate_and_clean()

    # 3. DELEGATE TO THE MAIN BRAIN
    # This service now raises AuthenticationError or InfrastructureError.
    response = await execute_login(
        credentials=clean_credentials,
        client_ip=client_ip,
        db=db
    )
    
    # 4. SECURE SUCCESS RESPONSE
    # Only reached if the credentials are valid and infrastructure is healthy.
    return response