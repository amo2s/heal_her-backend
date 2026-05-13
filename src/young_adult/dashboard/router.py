"""
src/young_adult/dashboard/router.py

The Dedicated GraphQL Router for the Young Adult Dashboard.
Separates general dashboard logic from the adult-focused AI services.
"""

import strawberry
from strawberry.fastapi import GraphQLRouter
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

# Import your database and the Young Adult-specific guard
from db import get_db
# [IMPORT UPGRADE]: Using the guard tailored for young adult authentication
from young_adult.heal_ai.guards import verify_young_adult_jwt_dependency 

# Import your new aggregated queries and mutations for Young Adults
from young_adult.dashboard.queries import YoungAdultDashboardQuery
from young_adult.dashboard.mutations import YoungAdultDashboardMutation

# ---------------------------------------------------------
# 1. THE SCHEMA DEFINITION
# ---------------------------------------------------------
young_adult_dashboard_schema = strawberry.Schema(
    query=YoungAdultDashboardQuery, 
    mutation=YoungAdultDashboardMutation
)

# ---------------------------------------------------------
# 2. THE CONTEXT INJECTOR
# ---------------------------------------------------------
async def get_dashboard_context(
    request: Request,
    db: AsyncSession = Depends(get_db),
    # Strict enforcement: Only verified young adults can access this dashboard logic
    user_context: dict = Depends(verify_young_adult_jwt_dependency) 
):
    """
    Bridges the FastAPI security layer with the Young Adult Dashboard resolvers.
    """
    return {
        "request": request, 
        "db": db, 
        "user_context": user_context 
    }

# ---------------------------------------------------------
# 3. THE ROUTER INSTANTIATION
# ---------------------------------------------------------
young_adult_dashboard_router = GraphQLRouter(
    young_adult_dashboard_schema,
    context_getter=get_dashboard_context,
    path="/young_adult/dashboard/graphql" # THE DEDICATED YOUNG ADULT ENDPOINT
)