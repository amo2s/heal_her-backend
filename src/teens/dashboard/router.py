"""
src/teens/dashboard/router.py

The Dedicated GraphQL Router for the Teens Dashboard.
Separates general dashboard logic (greetings, videos, etc.) from the AI service.
"""

import strawberry
from strawberry.fastapi import GraphQLRouter
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

# Import your database and the Teens-specific guard
from db import get_db
from teens.heal_ai.guards import verify_teen_jwt_dependency 

# Import your new aggregated queries and mutations
from teens.dashboard.queries import TeensDashboardQuery
from teens.dashboard.mutations import TeensDashboardMutation

# ---------------------------------------------------------
# 1. THE SCHEMA DEFINITION
# ---------------------------------------------------------
teens_dashboard_schema = strawberry.Schema(
    query=TeensDashboardQuery, 
    mutation=TeensDashboardMutation
)

# ---------------------------------------------------------
# 2. THE CONTEXT INJECTOR
# ---------------------------------------------------------
async def get_dashboard_context(
    request: Request,
    db: AsyncSession = Depends(get_db),
    # Strict enforcement: Only verified teens can access the dashboard logic
    user_context: dict = Depends(verify_teen_jwt_dependency) 
):
    """
    Bridges the FastAPI security layer with the Dashboard resolvers.
    """
    return {
        "request": request, 
        "db": db, 
        "user_context": user_context 
    }

# ---------------------------------------------------------
# 3. THE ROUTER INSTANTIATION
# ---------------------------------------------------------
teens_dashboard_router = GraphQLRouter(
    teens_dashboard_schema,
    context_getter=get_dashboard_context,
    path="/teens/dashboard/graphql" # THIS IS YOUR NEW SEPARATE ENDPOINT
)