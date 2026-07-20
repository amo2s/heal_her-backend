"""
src/terms/schema.py

The isolated GraphQL schema aggregation for the Terms/Legal domain.
Exports the configured GraphQLRouter to be mounted directly in main.py without bloat.
"""

import strawberry
from strawberry.fastapi import GraphQLRouter
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

# Import your domain mutations
from terms.mutations import LegalMutations

from db import get_db

@strawberry.type
class TermsQuery:
    """
    GraphQL requires at least one Query root. 
    This acts as a secure health check for the legal domain.
    """
    @strawberry.field
    def legal_matrix_status(self) -> str:
        return "Heal Her Legal Execution Matrix is online and secure."


@strawberry.type
class TermsMutation(LegalMutations):
    """
    Domain-specific mutation aggregator.
    If you add more mutation classes to the terms domain later, 
    simply add them to the inheritance list here: class TermsMutation(LegalMutations, FutureMutations):
    """
    pass


# Compile the strict domain schema
schema = strawberry.Schema(query=TermsQuery, mutation=TermsMutation)


async def get_graphql_context(db: AsyncSession = Depends(get_db)):
    """
    Injects the FastAPI database session directly into the Strawberry GraphQL context.
    This safely passes the `db` instance to info.context["db"] in your mutations.
    """
    return {"db": db}


# The single router packaged for main.py
terms_graphql_router = GraphQLRouter(
    schema,
    context_getter=get_graphql_context
)