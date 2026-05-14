"""
src/young_adult/heal_ai/router.py

The Central GraphQL Gateway for the Young Adult Heal AI.
Injects the verified Security Context and Database Session into every request.
Aligned with the HEAL Security Shield (Zero-Leak Policy).
"""

import strawberry
from strawberry.fastapi import GraphQLRouter
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

# [UPDATE]: Import central infrastructure
from db import get_db
# Uses the fortified guard which now raises Shield-compatible exceptions
from young_adult.heal_ai.guards import verify_young_adult_jwt_dependency 

# [UPDATE]: Isolated GraphQL Logic mapped to the Young Adult namespace
from young_adult.heal_ai.queries import HealAIQueries
from young_adult.heal_ai.mutations import HealAIMutations

# ---------------------------------------------------------
# 1. THE SCHEMA DEFINITION
# ---------------------------------------------------------
# [UPDATE]: Isolated schema for Young Adults to maintain domain boundary integrity.
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
    # [UPDATE]: Strict Guard Dependency. Now raises AuthenticationError 
    # handled by the global interceptor, preventing unauthenticated resolver execution.
    user_context: dict = Depends(verify_young_adult_jwt_dependency) 
):
    """
    Bridges FastAPI dependency injection with the Strawberry execution context.
    """
    return {
        "request": request, 
        "db": db, 
        "user_context": user_context  # Consumed by info.context["user_context"]
    }

# ---------------------------------------------------------
# 3. THE ROUTER INSTANTIATION
# ---------------------------------------------------------
# [UPDATE]: Endpoint instantiation with domain-specific pathing.
# Standardized to follow the segmented demographic routing logic.
graphql_router = GraphQLRouter(
    heal_ai_schema,
    context_getter=get_graphql_context,
    path="/young_adult/heal-ai/graphql"
)