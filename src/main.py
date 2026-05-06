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

# --- NEW: IMPORT MANAGEMENT AUTH (Signup & Login) ---
# Adjust the import paths if your signup module is named differently
from management.auth.login.mutations import AdminLoginMutation
from management.auth.signup.mutations import StaffAuthMutation

# --- NEW: IMPORT THE KIDS AI BUDDY ECOSYSTEM ---
from kids.ai_buddy.handlers.ai_buddy import router as ai_buddy_rest_router
from kids.ai_buddy.graphql.router import graphql_router as ai_buddy_graphql_router

# ---------------------------------------------------------
# 2. THE DUMMY QUERY (Required by GraphQL)
# ---------------------------------------------------------
@strawberry.type
class Query:
    @strawberry.field
    def health_check(self) -> str:
        return "Heal Her Vault is online and fortified."

# ---------------------------------------------------------
# 3. ROOT MUTATION (The Aggregator)
# ---------------------------------------------------------
# Multiple inheritance merges all distinct mutation classes into a single 
# unified GraphQL endpoint without duplicating any code.
@strawberry.type
class RootMutation(AuthMutation,StaffAuthMutation, AdminLoginMutation):
    pass

# ---------------------------------------------------------
# 4. THE SCHEMA CONFIGURATION
# ---------------------------------------------------------
# Using our vault settings! If DEBUG is False, IS_PROD is True.
IS_PROD = not settings.DEBUG

# The correct extension to lock down the schema
schema_extensions = [DisableIntrospection()] if IS_PROD else []

schema = strawberry.Schema(
    query=Query, 
    mutation=RootMutation, # Replaced AuthMutation with the aggregated RootMutation
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
        # Added strictly for Management Auth logic which expects "db"
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


# --- MOUNT THE KIDS AI BUDDY ECOSYSTEM ---

# 1. The REST endpoint for live SSE Streaming (/kids/ai-buddy/chat/stream)
app.include_router(ai_buddy_rest_router)

# 2. The separate, dedicated GraphQL endpoint for Kids Management (/kids/ai-buddy/graphql)
app.include_router(ai_buddy_graphql_router)


@app.get("/")
async def root():
    return {"message": "Heal Her API - Unauthorized Access is Prohibited."}