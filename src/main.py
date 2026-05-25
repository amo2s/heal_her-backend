from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from starlette.datastructures import MutableHeaders
from strawberry.fastapi import GraphQLRouter
import strawberry
from strawberry.extensions import DisableIntrospection

# --- 1. CORE INFRASTRUCTURE ---
from auth.graphql.mutations import AuthMutation
from auth.logout.mutations import LogoutMutation
from auth.password_reset.mutations import PasswordResetMutation
from db import get_db
from core.config import settings
from core.redis import verify_cache_connection

# --- MANAGEMENT ECOSYSTEM ---
from management.auth.login.mutations import AdminLoginMutation
from management.auth.signup.mutations import StaffAuthMutation
from management.dashboard.resolvers import DashboardQuery

# --- KIDS ECOSYSTEM ---
from kids.ai_buddy.handlers.ai_buddy import router as ai_buddy_rest_router
from kids.ai_buddy.graphql.router import graphql_router as ai_buddy_graphql_router
from kids.dashboard.router import kids_dashboard_router as kids_main_dashboard_router

# --- TEENS ECOSYSTEM ---
from teens.heal_ai.handlers import router as heal_ai_rest_router
from teens.heal_ai.router import graphql_router as heal_ai_graphql_router
from teens.dashboard.router import teens_dashboard_router as teens_main_dashboard_router

# --- YOUNG ADULTS ECOSYSTEM ---
from young_adult.dashboard.router import young_adult_dashboard_router as ya_main_dashboard_router
from young_adult.heal_ai.handlers import router as ya_heal_ai_rest_router
from young_adult.heal_ai.router import graphql_router as ya_heal_ai_graphql_router


# ---------------------------------------------------------
# 2. SCHEMA AGGREGATION
# ---------------------------------------------------------
@strawberry.type
class RootQuery(DashboardQuery):
    @strawberry.field
    def health_check(self) -> str:
        return "Heal Her Vault is online and fortified."


@strawberry.type
class RootMutation(
    AuthMutation, 
    LogoutMutation, 
    StaffAuthMutation, 
    AdminLoginMutation,
    PasswordResetMutation
):
    pass


IS_PROD = not settings.DEBUG
schema_extensions = [DisableIntrospection()] if IS_PROD else []

schema = strawberry.Schema(
    query=RootQuery, 
    mutation=RootMutation, 
    extensions=schema_extensions 
)


# ---------------------------------------------------------
# 3. CONTEXT & MIDDLEWARE (THE PURE ASGI UPGRADE)
# ---------------------------------------------------------
async def get_context(request: Request, background_tasks: BackgroundTasks, db = Depends(get_db)):
    """
    injects request, background tasks (for async audits), and db sessions globally.
    """
    return {
        "request": request,
        "background_tasks": background_tasks,
        "session": db, 
        "db": db,      
    }

class PureSecurityHeaderMiddleware:
    """
    A low-level ASGI middleware that injects strict security headers.
    By bypassing BaseHTTPMiddleware, it prevents context fragmentation 
    and keeps proxy headers fully intact for the GraphQL graph.
    """
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.append("X-Content-Type-Options", "nosniff")
                headers.append("X-Frame-Options", "DENY")
                headers.append("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
                headers.append("Referrer-Policy", "strict-origin-when-cross-origin")
            await send(message)

        await self.app(scope, receive, send_wrapper)


# ---------------------------------------------------------
# 4. APP INITIALIZATION & LIFESPAN
# ---------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    executes critical infrastructure checks before the vault accepts traffic.
    """
    await verify_cache_connection()
    yield

app = FastAPI(
    title="Heal Her Backend",
    version="1.0.0",
    docs_url=None if IS_PROD else "/docs",
    redoc_url=None if IS_PROD else "/redoc",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", 
        "https://healher.vercel.app" 
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"], 
    allow_headers=["Content-Type", "x-healher-handshake", "Authorization", "Accept"], 
)

# Apply the new Pure ASGI Shield
app.add_middleware(PureSecurityHeaderMiddleware)


# ---------------------------------------------------------
# 5. ABSOLUTE ROUTE MOUNTING
# ---------------------------------------------------------

# Global Auth/Main
graphql_app = GraphQLRouter(
    schema, 
    context_getter=get_context,
    graphql_ide="graphiql" if not IS_PROD else None
)
app.include_router(graphql_app, prefix="/graphql")

# Kids 
app.include_router(kids_main_dashboard_router)
app.include_router(ai_buddy_rest_router)
app.include_router(ai_buddy_graphql_router)

# Teens
app.include_router(teens_main_dashboard_router)
app.include_router(heal_ai_rest_router)
app.include_router(heal_ai_graphql_router)

# Young Adults
app.include_router(ya_main_dashboard_router)
app.include_router(ya_heal_ai_rest_router)
app.include_router(ya_heal_ai_graphql_router)


# ---------------------------------------------------------
# 6. HEALTH CHECK ENDPOINTS
# ---------------------------------------------------------
@app.get("/", tags=["Health"])
@app.get("/health", tags=["Health"])
async def root():
    """
    prevents empty pages and provides monitoring uptime status.
    """
    return {
        "status": "online",
        "message": "Heal Her Vault API is active. Unauthorized access is prohibited.",
        "environment": "production" if IS_PROD else "development"
    }