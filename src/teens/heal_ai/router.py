"""
src/teens/heal_ai/router.py

The Central GraphQL Gateway for the Teens Heal AI.
Injects the verified Security Context and Database Session into every request.
Aligned with the HEAL Security Shield (Zero-Leak Policy).
"""

import strawberry
from strawberry.fastapi import GraphQLRouter
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

# [DOCUMENTATION]: Import central infrastructure
from db import get_db
# Uses the fortified guard which now raises Shield-compatible exceptions
from teens.heal_ai.guards import verify_teen_jwt_dependency 

# [DOCUMENTATION]: Isolated GraphQL Logic mapped to the Teens namespace
from teens.heal_ai.queries import HealAIQueries
from teens.heal_ai.mutations import HealAIMutations

# ---------------------------------------------------------
# 1. THE SCHEMA DEFINITION
# ---------------------------------------------------------
# [UPDATE]: Isolated schema for Teens to maintain domain boundary integrity.
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
    user_context: dict = Depends(verify_teen_jwt_dependency) 
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
graphql_router = GraphQLRouter(
    heal_ai_schema,
    context_getter=get_graphql_context,
    path="/teens/heal-ai/graphql"
)