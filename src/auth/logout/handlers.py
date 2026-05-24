import logging
from datetime import datetime, timezone
import strawberry
from fastapi import BackgroundTasks

# central imports based on your heal her architecture
from core.exceptions import AuthenticationError, InfrastructureError

# strict internal imports using your exact separation of concerns
from auth.logout.schemas import LogoutResponse
from auth.logout.guards import enforce_logout_guard
from auth.logout.services import execute_logout_service

logger = logging.getLogger("HEAL_SECURITY")
logger.setLevel(logging.WARNING)

async def handle_logout_mutation(info: strawberry.Info, refresh_token: str) -> LogoutResponse:
    """
    the orchestration layer.
    coordinates the guard and service, sanitizes exceptions, and formats the final schema.
    """
    try:
        # 1. extract background tasks from the graphql context
        background_tasks: BackgroundTasks = info.context.get("background_tasks")
        if not background_tasks:
            logger.critical("[ORCHESTRATION] background_tasks missing from strawberry context")
            raise InfrastructureError(internal_message="Server misconfiguration.")

        # 2. pass the raw request through the cryptographic bouncer
        # the guard will raise an AuthenticationError if anything is tampered with
        clean_payload = await enforce_logout_guard(info, refresh_token)

        # 3. execute the atomic vault service
        # the service will raise an InfrastructureError if valkey goes down
        success = await execute_logout_service(clean_payload, background_tasks)

        # 4. package the final zero-leakage response
        if success:
            return LogoutResponse(
                status="revoked",
                message="Session securely terminated.",
                revoked_at=datetime.now(timezone.utc)
            )

    except (AuthenticationError, InfrastructureError):
        # let your custom predefined shield errors bubble up directly
        raise
    except Exception as e:
        # 5. the ultimate blast shield
        # catches random python crashes and morphs them into safe uniform errors
        logger.error(f"[BLAST SHIELD] unhandled exception in logout handler: {str(e)}")
        raise AuthenticationError(internal_message="Authentication failed.")