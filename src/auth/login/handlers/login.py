from strawberry.types import Info
from graphql import GraphQLError
from pydantic import ValidationError

# Adjust imports to match your project structure
from auth.login.schemas.login import LoginInput, LoginResponse
from auth.login.services.login import execute_login

async def handle_login(info: Info, input_data: LoginInput) -> LoginResponse:
    """
    The orchestrator for the login flow. 
    Sits between the GraphQL endpoint and the Service Brain.
    """
    # 1. EXTRACT CONTEXT
    request = info.context["request"]
    db = info.context["session"]
    
    # --- THE PROXY FIX: EXTRACT REAL IP ---
    # Next.js sends the real user's IP inside this header
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # Pick the first IP if there are multiple proxies chained
        client_ip = forwarded_for.split(",")[0].strip()
    else:
        # Fallback just in case
        client_ip = request.client.host

    # 2. TRIGGER THE PYDANTIC FIREWALL
    try:
        clean_credentials = input_data.validate_and_clean()
    except ValidationError as e:
        # Catch DoS payloads or bad formatting immediately
        error_msg = e.errors()[0]["msg"]
        raise GraphQLError(f"Validation Error: {error_msg}")

    # 3. DELEGATE TO THE MAIN BRAIN
    try:
        # This will now receive the dual-token payload (access + refresh) from our updated service
        response = await execute_login(
            credentials=clean_credentials,
            client_ip=client_ip,
            db=db
        )
        return response
        
    except GraphQLError as e:
        # Pass intentional security errors directly to the client (e.g., "Invalid credentials")
        raise e
    except Exception as e:
        # 4. THE ULTIMATE FAILSAFE
        # Catch database crashes or Valkey timeouts and log them silently.
        print(f"[CRITICAL LOGIN EXCEPTION] IP: {client_ip} - Error: {str(e)}")
        raise GraphQLError("Heal Her Security: Internal systems offline. Please try again later.")