from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from strawberry.fastapi import GraphQLRouter
import strawberry
from strawberry.extensions import DisableIntrospection

# --- 1. IMPORT YOUR SECURE MUTATIONS & DB ---
from auth.graphql.mutations import AuthMutation
from db import get_db
from core.config import settings

# --- IMPORT MANAGEMENT AUTH (Signup & Login) ---
from management.auth.login.mutations import AdminLoginMutation
from management.auth.signup.mutations import StaffAuthMutation

# --- IMPORT MANAGEMENT DASHBOARD (The Core Operations) ---
from management.dashboard.resolvers import DashboardQuery

# --- IMPORT THE KIDS ECOSYSTEM ---
from kids.ai_buddy.handlers.ai_buddy import router as ai_buddy_rest_router
from kids.ai_buddy.graphql.router import graphql_router as ai_buddy_graphql_router
from kids.dashboard.router import kids_dashboard_router as kids_main_dashboard_router

# --- IMPORT THE TEENS ECOSYSTEM ---
from teens.heal_ai.handlers import router as heal_ai_rest_router
from teens.heal_ai.router import graphql_router as heal_ai_graphql_router
from teens.dashboard.router import teens_dashboard_router as teens_main_dashboard_router

# ---------------------------------------------------------
# 2. ROOT QUERY (The Aggregator)
# ---------------------------------------------------------
# Inheriting DashboardQuery automatically mounts getMe into the global schema
@strawberry.type
class RootQuery(DashboardQuery):
    @strawberry.field
    def health_check(self) -> str:
        return "Heal Her Vault is online and fortified."

# ---------------------------------------------------------
# 3. ROOT MUTATION (The Aggregator)
# ---------------------------------------------------------
# Multiple inheritance merges all distinct mutation classes into a single 
# unified GraphQL endpoint without duplicating any code.
@strawberry.type
class RootMutation(AuthMutation, StaffAuthMutation, AdminLoginMutation):
    pass

# ---------------------------------------------------------
# 4. THE SCHEMA CONFIGURATION
# ---------------------------------------------------------
# Using our vault settings! If DEBUG is False, IS_PROD is True.
IS_PROD = not settings.DEBUG

# The correct extension to lock down the schema
schema_extensions = [DisableIntrospection()] if IS_PROD else []

schema = strawberry.Schema(
    query=RootQuery, 
    mutation=RootMutation, 
    extensions=schema_extensions 
)

# ---------------------------------------------------------
# 5. THE CONTEXT GETTER (The Guard's Eyes & The DB Bridge)
# ---------------------------------------------------------
async def get_context(
    request: Request, 
    db = Depends(get_db) 
):
    return {
        "request": request,
        # Kept for backward compatibility so your existing AuthMutation doesn't break
        "session": db, 
        # Added strictly for Management Auth/Dashboard logic which expects "db"
        "db": db,      
    }

# ---------------------------------------------------------
# 6. SECURITY MIDDLEWARE (The Header Shield)
# ---------------------------------------------------------
class SecurityHeaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

# ---------------------------------------------------------
# 7. INITIALIZE THE FORTRESS
# ---------------------------------------------------------
app = FastAPI(
    title="Heal Her Backend",
    version="1.0.0",
    docs_url=None if IS_PROD else "/docs",
    redoc_url=None if IS_PROD else "/redoc"
)

# CORS kept strictly to your specifications (Same Origin logic)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", 
        "https://your-frontend.vercel.app" 
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"], 
    allow_headers=["Content-Type", "x-healher-handshake", "Authorization", "Accept"], 
)

app.add_middleware(SecurityHeaderMiddleware)

# --- THE CORE GRAPHQL ROUTE (Unified Auth/Main) ---
graphql_app = GraphQLRouter(
    schema, 
    context_getter=get_context,
    graphql_ide="graphiql" if not IS_PROD else None
)
app.include_router(graphql_app, prefix="/graphql")


# --- MOUNT THE KIDS ECOSYSTEM ---
app.include_router(kids_main_dashboard_router)
app.include_router(ai_buddy_rest_router)
app.include_router(ai_buddy_graphql_router)


# --- MOUNT THE TEENS ECOSYSTEM ---
app.include_router(teens_main_dashboard_router)
app.include_router(heal_ai_rest_router)
app.include_router(heal_ai_graphql_router)


@app.get("/")
async def root():
    return {"message": "Heal Her API - Unauthorized Access is Prohibited."}