import logging
from pydantic import ValidationError
import strawberry
from strawberry.types import Info

# Import the fortified schemas
from auth.password_reset.schemas import (
    RequestOTPInput, VerifyOTPInput, ResetPasswordInput,
    RequestOTPPayload, VerifyOTPPayload, ResetPasswordPayload,
    StandardResetResponse, VerifyOTPResponse
)

# Import the core cryptographic services
from auth.password_reset.services import (
    request_password_reset_service,
    verify_reset_otp_service,
    confirm_password_reset_service
)

# Import central security exceptions
from core.exceptions import AuthenticationError, InfrastructureError

logger = logging.getLogger("HEAL_SECURITY")
logger.setLevel(logging.WARNING)


async def request_password_reset_handler(input_data: RequestOTPInput, info: Info) -> StandardResetResponse:
    """
    PHASE 1 HANDLER: Unpacks the email, strictly validates it via Pydantic, 
    and provisions the SQLAlchemy session to the service layer.
    """
    try:
        # 1. Pydantic Conversion Gateway
        payload = RequestOTPPayload(email=input_data.email)

        # 2. Context Extraction
        db = info.context.get("db")
        if not db:
            raise InfrastructureError(internal_message="Database session missing from context.")

        # 3. Execute Core Service
        result = await request_password_reset_service(email=payload.email, db=db)
        return StandardResetResponse(status=result["status"], message=result["message"])

    except ValidationError as e:
        logger.warning(f"[PAYLOAD REJECTED] Validation failed for OTP request: {e.errors()}")
        return StandardResetResponse(
            status="error",
            message="Invalid payload format. Please verify your input."
        )
    except (AuthenticationError, InfrastructureError):
        # We drop the exception silently. Handlers log internally, clients get a blank shield.
        return StandardResetResponse(
            status="error",
            message="Service unavailable or security protocol violation."
        )
    except Exception as e:
        logger.critical(f"[FATAL ORCHESTRATION CRASH] Unhandled exception in request handler: {str(e)}")
        return StandardResetResponse(
            status="error",
            message="An unexpected internal error occurred."
        )


async def verify_reset_otp_handler(input_data: VerifyOTPInput, info: Info) -> VerifyOTPResponse:
    """
    PHASE 2 HANDLER: Blocks brute-force SQL injections by forcing the OTP 
    through the strict 6-digit regex Pydantic schema before validation.
    """
    try:
        payload = VerifyOTPPayload(email=input_data.email, otp_code=input_data.otp_code)

        # Execute Core Service
        reset_token = await verify_reset_otp_service(email=payload.email, otp_code=payload.otp_code)
        
        return VerifyOTPResponse(
            status="success",
            message="Authorization successful. Please proceed to update your vault.",
            reset_token=reset_token
        )

    except ValidationError as e:
        logger.warning(f"[PAYLOAD REJECTED] Validation failed for OTP verify: {e.errors()}")
        return VerifyOTPResponse(
            status="error",
            message="Invalid payload format. Please verify your input.",
            reset_token=None
        )
    except AuthenticationError:
        return VerifyOTPResponse(
            status="error",
            message="Invalid or expired authorization code.",
            reset_token=None
        )
    except InfrastructureError:
        return VerifyOTPResponse(
            status="error",
            message="Service unavailable or security protocol violation.",
            reset_token=None
        )
    except Exception as e:
        logger.critical(f"[FATAL ORCHESTRATION CRASH] Unhandled exception in verify handler: {str(e)}")
        return VerifyOTPResponse(
            status="error",
            message="An unexpected internal error occurred.",
            reset_token=None
        )


async def confirm_password_reset_handler(input_data: ResetPasswordInput, info: Info) -> StandardResetResponse:
    """
    PHASE 3 HANDLER: Validates strict password complexity and confirms that 
    the new passwords match perfectly before ever touching the database.
    """
    try:
        # The Pydantic model natively checks if new_password == confirm_password
        payload = ResetPasswordPayload(
            reset_token=input_data.reset_token,
            new_password=input_data.new_password,
            confirm_password=input_data.confirm_password
        )

        db = info.context.get("db")
        if not db:
            raise InfrastructureError(internal_message="Database session missing from context.")

        result = await confirm_password_reset_service(
            reset_token=payload.reset_token, 
            new_password=payload.new_password, 
            db=db
        )
        
        return StandardResetResponse(status=result["status"], message=result["message"])

    except ValidationError as e:
        logger.warning(f"[PAYLOAD REJECTED] Validation failed for password confirm: {e.errors()}")
        return StandardResetResponse(
            status="error",
            message="Password does not meet security constraints or passwords do not match."
        )
    except AuthenticationError:
        return StandardResetResponse(
            status="error",
            message="Invalid or expired reset token sequence."
        )
    except InfrastructureError:
        return StandardResetResponse(
            status="error",
            message="Service unavailable or security protocol violation."
        )
    except Exception as e:
        logger.critical(f"[FATAL ORCHESTRATION CRASH] Unhandled exception in confirm handler: {str(e)}")
        return StandardResetResponse(
            status="error",
            message="An unexpected internal error occurred."
        )