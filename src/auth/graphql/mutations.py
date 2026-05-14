import strawberry
from auth.signup.handlers.signup import SignupHandler
from auth.login.handlers.login import handle_login
from auth.guards import LoginFortressGuard

# [UPDATE]: Import the refined, logic-shielded refresh handler
from auth.login.handlers.refresh import handle_refresh

@strawberry.type
class AuthMutation(SignupHandler):
    """
    The main mutation entry point for all Authentication actions.
    This class aggregates our secured handlers into the GraphQL schema.
    
    [DOCUMENTATION]: 
    - No manual error catching (try/except) is allowed here.
    - All security events bubble up to the Security Shield for sanitization.
    """
    
    # 1. THE SIGNUP GATE
    # [DOCUMENTATION]: Inherited from SignupHandler. 
    # This natively registers the `signup` mutation. 
    # Changes made to the SignupHandler class (Skinny pattern) are automatically reflected here.

    # 2. THE LOGIN GATE
    # The impenetrable login endpoint. 
    # [UPDATE]: Permission classes are the first line of defense.
    # The LoginFortressGuard (Dual-Axis Bear Trap) will drop the connection 
    # if an IP or Email is currently locked out BEFORE the resolver executes.
    login = strawberry.mutation(
        resolver=handle_login,
        permission_classes=[LoginFortressGuard]
    )

    # 3. THE REFRESH GATE
    # The silent Negotiator. Takes the 7-day refresh token and issues fresh keys.
    # [UPDATE]: Wired to the refined handle_refresh logic.
    # Logic: Uses unverified claim peeking to route the request to the correct 
    # security domain (Kid/Teen/Young-Adult) without manual decoding logic in the mutation.
    refresh_token = strawberry.mutation(
        resolver=handle_refresh
    )