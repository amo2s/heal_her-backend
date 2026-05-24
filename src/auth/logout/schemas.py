import strawberry
from datetime import datetime

@strawberry.type
class LogoutResponse:
    """
    strict zero-leakage boundary. 
    returns only the absolute minimum required by the frontend proxy to confirm the session is dead.
    """
    status: str = strawberry.field(
        description="strict state marker, expected to be 'revoked'."
    )
    message: str = strawberry.field(
        description="clean sanitized confirmation message for the user."
    )
    revoked_at: datetime = strawberry.field(
        description="exact utc timestamp when the valkey blacklist was sealed."
    )