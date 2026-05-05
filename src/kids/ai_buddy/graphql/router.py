"""
kids/ai_buddy/router.py

The Central GraphQL Gateway for the Kids AI Buddy.
Injects the verified Security Context and Database Session into every request.
"""

import strawberry
from strawberry.fastapi import GraphQLRouter
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

# Import your central infrastructure
from db import get_db
from kids.ai_buddy.guards import verify_kids_jwt_dependency 

# Clean, separated GraphQL Logic
from kids.ai_buddy.graphql.queries import AIBuddyQueries
from kids.ai_buddy.graphql.mutations import AIBuddyMutations

# ---------------------------------------------------------
# 1. THE SCHEMA DEFINITION
# ---------------------------------------------------------
# We combine Queries (Reads) and Mutations (Writes) into a single schema
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
    """
    return {
        "request": request, 
        "db": db, 
        "user_context": user_context  # Matches info.context["user_context"] in queries.py
    }

# ---------------------------------------------------------
# 3. THE ROUTER INSTANTIATION
# ---------------------------------------------------------
# This creates the physical endpoint on your API
graphql_router = GraphQLRouter(
    ai_buddy_schema,
    context_getter=get_graphql_context,
    path="/kids/ai-buddy/graphql"
)