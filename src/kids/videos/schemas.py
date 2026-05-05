from pydantic import BaseModel, Field, HttpUrl, field_validator, ConfigDict
from typing import Annotated, Optional

# =====================================================================
# THE REGEX REGISTRY (The Extremist's Patterns)
# =====================================================================
# Allow alphanumeric, spaces, and basic kid-friendly punctuation only.
TITLE_PATTERN = r"^[a-zA-Z0-9\s\?\!\.\,\-\']+$"
# Format: MM:SS or HH:MM:SS
DURATION_PATTERN = r"^(\d{1,2}:)?([0-5]?[0-9]):([0-5][0-9])$"
# Strict UUIDv4 Pattern to prevent SQL injection via ID fields
UUID_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
# Strict Alphabet and Space only for topics
TOPIC_PATTERN = r"^[a-zA-Z\s]+$"
# Broader pattern specifically for safe search bar inputs
SEARCH_PATTERN = r"^[a-zA-Z0-9\s\?\!\.\,\-\']+$"

# =====================================================================
# 1. THE VIDEO CREATION SCHEMA (The Physical Input Firewall)
# =====================================================================
class KidVideoCreateSchema(BaseModel):
    """
    Validates data when adding a new video to the system.
    """
    model_config = ConfigDict(
        extra='forbid',              # Brutal: Reject any unknown fields immediately
        str_strip_whitespace=True    # Clean all strings automatically
    )

    title: Annotated[str, Field(min_length=3, max_length=100, pattern=TITLE_PATTERN)]
    topic: Annotated[str, Field(min_length=2, max_length=50, pattern=TOPIC_PATTERN)]
    duration: Annotated[str, Field(pattern=DURATION_PATTERN)]
    
    # We use HttpUrl to enforce protocol at the Pydantic level
    thumbnail_url: HttpUrl
    video_url: HttpUrl
    
    # Transcripts can be large, but we cap them to prevent memory exhaustion DoS
    transcript: Annotated[str, Field(min_length=10, max_length=50000)]

    @field_validator("thumbnail_url", "video_url", mode="after")
    @classmethod
    def enforce_https(cls, v: HttpUrl) -> str:
        """Forces all media to be served over secure connections."""
        if v.scheme != "https":
            raise ValueError("Insecure protocol detected. HTTPS is mandatory.")
        return str(v)


# =====================================================================
# 2. THE PROGRESS UPDATE SCHEMA (The User-State Firewall)
# =====================================================================
class KidVideoProgressUpdateSchema(BaseModel):
    """
    Validates the heartbeat payload sent from the frontend video player.
    """
    model_config = ConfigDict(extra='forbid')

    # Ensure the video_id is a valid UUID format before it even touches the DB router
    video_id: Annotated[str, Field(pattern=UUID_PATTERN)]
    
    # Brutal boundary check: No floats, no negatives, no > 100.
    watched_percentage: Annotated[int, Field(ge=0, le=100)]


# =====================================================================
# 3. THE QUERY SCHEMA (Filtering Firewall)
# =====================================================================
class KidVideoFilterSchema(BaseModel):
    """
    Validates search and filter arguments to prevent NoSQL/SQL injection via search bars.
    Matches the arguments defined in the queries.py read-gate.
    """
    model_config = ConfigDict(
        extra='forbid',
        str_strip_whitespace=True
    )

    # Uses SEARCH_PATTERN so queries like "Stranger Game 2!" don't fail validation
    search_query: Optional[Annotated[str, Field(min_length=2, max_length=50, pattern=SEARCH_PATTERN)]] = None
    topic: Optional[Annotated[str, Field(min_length=2, max_length=50, pattern=TOPIC_PATTERN)]] = None
    limit: Annotated[int, Field(ge=1, le=50)] = 20  # Hard cap on pagination to prevent DB lockups