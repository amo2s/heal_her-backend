import strawberry
from auth.signup.handlers.signup import SignupHandler
from auth.login.handlers.login import handle_login
from auth.guards import LoginFortressGuard

# ADDED: Import the new refresh handler
from auth.login.handlers.refresh import handle_refresh

@strawberry.type
class AuthMutation(SignupHandler):
    """
    The main mutation entry point for all Authentication actions.
    This class aggregates our secured handlers into the GraphQL schema.
    """
    
    # 1. THE SIGNUP GATE
    # By inheriting from SignupHandler above, Strawberry natively registers the 
    # `signup` mutation here, fully intact with its `age: int` requirement 
    # and the SignupFortressGuard. We don't need to manually assign it!

    # 2. THE LOGIN GATE
    # The impenetrable login endpoint. 
    # We attach the Dual-Axis Bear Trap (LoginFortressGuard) right at the gate.
    # If the guard fails, handle_login is never even executed.
    login = strawberry.mutation(
        resolver=handle_login,
        permission_classes=[LoginFortressGuard]
    )

    # 3. THE REFRESH GATE (NEW)
    # The silent Negotiator. Takes the 7-day refresh token and issues fresh keys.
    # We do NOT put the LoginFortressGuard here, because the user is already logged in.
    refresh_token = strawberry.mutation(
        resolver=handle_refresh
    )