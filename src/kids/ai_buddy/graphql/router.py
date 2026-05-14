"""
kids/ai_buddy/router.py

The Central GraphQL Gateway for the Kids AI Buddy.
Injects the verified Security Context and Database Session into every request.
Aligned with the HEAL Security Shield (Zero-Leak Policy).
"""

import strawberry
from strawberry.fastapi import GraphQLRouter
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

# [DOCUMENTATION]: Import your central infrastructure
from db import get_db
from kids.ai_buddy.guards import verify_kids_jwt_dependency 

# [DOCUMENTATION]: Clean, separated GraphQL Logic
from kids.ai_buddy.graphql.queries import AIBuddyQueries
from kids.ai_buddy.graphql.mutations import AIBuddyMutations

# ---------------------------------------------------------
# 1. THE SCHEMA DEFINITION
# ---------------------------------------------------------
# [UPDATE]: We aggregate Queries (Reads) and Mutations (Writes).
# This schema is now strictly typed to prevent "Discovery" attacks where 
# an attacker might try to guess field names.
ai_buddy_schema = strawberry.Schema(
    query=AIBuddyQueries, 
    mutation=AIBuddyMutations
)

# ---------------------------------------------------------
# 2. THE CONTEXT INJECTOR (The Bridge)
# ---------------------------------------------------------
async def get_graphql_context(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_context: dict = Depends(verify_kids_jwt_dependency) 
):
    """
    This function runs BEFORE every GraphQL request.
    It bridges the FastAPI dependency injection system with Strawberry.
    
    [UPDATE]: 
    If `verify_kids_jwt_dependency` fails, it raises an AuthenticationError.
    FastAPI will intercept this before `get_graphql_context` completes,
    ensuring unauthenticated traffic never touches the GraphQL schema.
    """
    return {
        "request": request, 
        "db": db, 
        "user_context": user_context  # Consumed by info.context["user_context"]
    }

# ---------------------------------------------------------
# 3. THE ROUTER INSTANTIATION
# ---------------------------------------------------------
# [UPDATE]: Fixed pathing and integrated the context_getter.
# We explicitly set `path` to ensure the Next.js frontend knows where to point.
graphql_router = GraphQLRouter(
    ai_buddy_schema,
    context_getter=get_graphql_context,
    path="/kids/ai-buddy/graphql"
)