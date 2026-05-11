"""Shared Pydantic schema building blocks."""

from pydantic import BaseModel, ConfigDict


class APIModel(BaseModel):
    """Base for response schemas — reads attributes off ORM objects."""

    model_config = ConfigDict(from_attributes=True)


class HealthResponse(BaseModel):
    status: str = "ok"
    env: str
