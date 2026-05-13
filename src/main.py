from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from strawberry.fastapi import GraphQLRouter
import strawberry
from strawberry.extensions import DisableIntrospection

# --- 1. CORE INFRASTRUCTURE ---
from auth.graphql.mutations import AuthMutation
from db import get_db
from core.config import settings

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

# --- YOUNG ADULTS ECOSYSTEM (Updated Paths) ---
# [FIXED]: Updated to 'young_adults' and included the missing GraphQL router
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
class RootMutation(AuthMutation, StaffAuthMutation, AdminLoginMutation):
    pass

IS_PROD = not settings.DEBUG
schema_extensions = [DisableIntrospection()] if IS_PROD else []

schema = strawberry.Schema(
    query=RootQuery, 
    mutation=RootMutation, 
    extensions=schema_extensions 
)

# ---------------------------------------------------------
# 3. CONTEXT & MIDDLEWARE
# ---------------------------------------------------------
async def get_context(request: Request, db = Depends(get_db)):
    return {
        "request": request,
        "session": db, 
        "db": db,      
    }

class SecurityHeaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

# ---------------------------------------------------------
# 4. APP INITIALIZATION
# ---------------------------------------------------------
app = FastAPI(
    title="Heal Her Backend",
    version="1.0.0",
    docs_url=None if IS_PROD else "/docs",
    redoc_url=None if IS_PROD else "/redoc"
)

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

# ---------------------------------------------------------
# 5. ABSOLUTE ROUTE MOUNTING (Option C)
# ---------------------------------------------------------
# Under Option C, we remove prefixes here. 
# Sub-routers MUST define their full paths (e.g., path="/young_adults/...")

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

# Young Adults (Complete mounting)
# [FIXED]: All prefixes removed. Full paths are handled in the specific router files.
app.include_router(ya_main_dashboard_router)
app.include_router(ya_heal_ai_rest_router)
app.include_router(ya_heal_ai_graphql_router)

@app.get("/")
async def root():
    return {"message": "Heal Her API - Unauthorized Access is Prohibited."}