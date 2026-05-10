"""
src/kids/dashboard/router.py

The Dedicated GraphQL Router for the Kids Dashboard.
Separates general dashboard logic (greetings, videos, etc.) from the AI service.
"""

import strawberry
from strawberry.fastapi import GraphQLRouter
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

# Import your database and the Kids-specific guard
from db import get_db
# [IMPORT UPGRADE]: Using the kids-specific security guard
from kids.ai_buddy.guards import verify_kids_jwt_dependency 

# Import your new aggregated queries and mutations for the Kids sector
from kids.dashboard.queries import KidsDashboardQuery
from kids.dashboard.mutations import KidsDashboardMutation

# ---------------------------------------------------------
# 1. THE SCHEMA DEFINITION
# ---------------------------------------------------------
kids_dashboard_schema = strawberry.Schema(
    query=KidsDashboardQuery, 
    mutation=KidsDashboardMutation
)

# ---------------------------------------------------------
# 2. THE CONTEXT INJECTOR
# ---------------------------------------------------------
async def get_dashboard_context(
    request: Request,
    db: AsyncSession = Depends(get_db),
    # Strict enforcement: Only verified kids can access the dashboard logic
    user_context: dict = Depends(verify_kids_jwt_dependency) 
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
kids_dashboard_router = GraphQLRouter(
    kids_dashboard_schema,
    context_getter=get_dashboard_context,
    path="/kids/dashboard/graphql" # THIS IS YOUR NEW SEPARATE ENDPOINT FOR KIDS
)