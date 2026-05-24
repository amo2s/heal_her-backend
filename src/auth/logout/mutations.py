import strawberry
from auth.logout.schemas import LogoutResponse
from auth.logout.handlers import handle_logout_mutation

@strawberry.type
class LogoutMutation:
    """
    the naked routing layer.
    registers the mutation with strawberry and delegates everything to the handler.
    """
    
    @strawberry.mutation(
        description="securely terminates a user session, blacklists the token, and logs the security event."
    )
    async def logout(
        self, 
        info: strawberry.Info, 
        refresh_token: str = strawberry.argument(
            description="the 7-day refresh token to be revoked and permanently blacklisted."
        )
    ) -> LogoutResponse:
        
        # directly offload the context and the token to the orchestration layer
        # zero logic happens here.
        return await handle_logout_mutation(info, refresh_token)