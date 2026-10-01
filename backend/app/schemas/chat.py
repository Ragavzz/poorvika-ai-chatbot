"""Pydantic schemas for Chat API."""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        description="The customer's shopping query or prompt",
        examples=["Suggest headphones under 1500 with good ratings"]
    )


class ChatResponse(BaseModel):
    response: str = Field(
        ...,
        description="AI shopping assistant response grounded in PostgreSQL product catalog",
        examples=["Here are the top headphones matching your budget..."]
    )
