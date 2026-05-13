"""
src/young_adult/heal_ai/router.py

The Central GraphQL Gateway for the Young Adult Heal AI.
Injects the verified Security Context and Database Session into every request.
"""

import strawberry
from strawberry.fastapi import GraphQLRouter
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

# Import your central infrastructure (Paths use underscores)
from db import get_db
from young_adult.heal_ai.guards import verify_young_adult_jwt_dependency 

# Clean, separated GraphQL Logic mapped to the Young Adult namespace
# Note: Pointing to the graphql directory based on our previous file creations
from young_adult.heal_ai.queries import HealAIQueries
from young_adult.heal_ai.mutations import HealAIMutations

# ---------------------------------------------------------
# 1. THE SCHEMA DEFINITION
# ---------------------------------------------------------
# Combine Queries (Reads) and Mutations (Writes) into a single, isolated schema
heal_ai_schema = strawberry.Schema(
    query=HealAIQueries, 
    mutation=HealAIMutations
)

# ---------------------------------------------------------
# 2. THE CONTEXT INJECTOR (The Bridge)
# ---------------------------------------------------------
async def get_graphql_context(
    request: Request,
    db: AsyncSession = Depends(get_db),
    # Strict enforcement: Only tokens with the 'young_adult' role will pass this guard
    user_context: dict = Depends(verify_young_adult_jwt_dependency) 
):
    """
    This function runs BEFORE every GraphQL request.
    It bridges the FastAPI dependency injection system with Strawberry,
    ensuring the secure user identity is available to all resolvers.
    """
    return {
        "request": request, 
        "db": db, 
        "user_context": user_context  # Used by info.context["user_context"] in queries and mutations
    }

# ---------------------------------------------------------
# 3. THE ROUTER INSTANTIATION
# ---------------------------------------------------------
# This creates the physical endpoint on your API, isolated for the young-adult demographic (Endpoint uses hyphens)
graphql_router = GraphQLRouter(
    heal_ai_schema,
    context_getter=get_graphql_context,
    path="/young_adult/heal-ai/graphql"
)