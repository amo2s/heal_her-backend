"""
src/young_adult/heal_ai/types.py

Isolated GraphQL Type Registry for the Young Adult Heal AI.
Prevents circular import errors between queries.py and mutations.py.
"""

import strawberry
from typing import Optional

@strawberry.type
class YoungAdultChatSessionType:
    id: str
    user_id: str
    title: Optional[str]
    is_deleted: bool
    created_at: str
    updated_at: str