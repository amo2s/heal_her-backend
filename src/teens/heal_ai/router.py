"""
src/teens/heal_ai/router.py

The Central GraphQL Gateway for the Teens Heal AI.
Injects the verified Security Context and Database Session into every request.
"""

import strawberry
from strawberry.fastapi import GraphQLRouter
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

# Import your central infrastructure
from db import get_db
# Updated import to use the singular function name
from teens.heal_ai.guards import verify_teen_jwt_dependency 

# Clean, separated GraphQL Logic mapped to the Teens namespace
from teens.heal_ai.queries import HealAIQueries
from teens.heal_ai.mutations import HealAIMutations

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
    # Strict enforcement: Only tokens with the 'teen' role will pass this guard
    user_context: dict = Depends(verify_teen_jwt_dependency) 
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
# This creates the physical endpoint on your API, isolated for the teens demographic
graphql_router = GraphQLRouter(
    heal_ai_schema,
    context_getter=get_graphql_context,
    path="/teens/heal-ai/graphql"
)