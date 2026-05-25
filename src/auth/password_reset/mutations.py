import strawberry
from strawberry.types import Info

# strict import of your fortified graphql input schemas and response types
from auth.password_reset.schemas import (
    RequestOTPInput,
    VerifyOTPInput,
    ResetPasswordInput,
    StandardResetResponse,
    VerifyOTPResponse
)

# strict import of your orchestration blast shields
from auth.password_reset.handlers import (
    request_password_reset_handler,
    verify_reset_otp_handler,
    confirm_password_reset_handler
)

# the iron dome guard
from auth.password_reset.guards import PasswordResetGuard

@strawberry.type
class PasswordResetMutation:
    """
    the absolute root exposure layer for the heal her password recovery graph.
    zero state modification. completely shielded by the valkey iron dome.
    """

    @strawberry.mutation(permission_classes=[PasswordResetGuard])
    async def request_password_reset(self, input: RequestOTPInput, info: Info) -> StandardResetResponse:
        """
        phase 1: intercepts the email, clears the guard, and triggers the async mailer.
        """
        return await request_password_reset_handler(input_data=input, info=info)

    @strawberry.mutation(permission_classes=[PasswordResetGuard])
    async def verify_reset_otp(self, input: VerifyOTPInput, info: Info) -> VerifyOTPResponse:
        """
        phase 2: intercepts the 6-digit guess, clears the strike-rule guard, and validates.
        """
        return await verify_reset_otp_handler(input_data=input, info=info)

    @strawberry.mutation(permission_classes=[PasswordResetGuard])
    async def confirm_password_reset(self, input: ResetPasswordInput, info: Info) -> StandardResetResponse:
        """
        phase 3: intercepts the new password payload, clears the guard, and locks the database.
        """
        return await confirm_password_reset_handler(input_data=input, info=info)