"""Validated context and generated questions for the suggestion popup."""

from typing import Annotated
from pydantic import BaseModel, Field, StrictStr, field_validator


class SuggestionProduct(BaseModel):
    id: str | None = Field(default=None, max_length=180)
    name: str = Field(min_length=1, max_length=300)
    brand: str | None = Field(default=None, max_length=150)
    category: str | None = Field(default=None, max_length=150)
    price: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    description: str | None = Field(default=None, max_length=4000)
    specifications: dict[str, str | int | float] | list[dict[str, str | int | float]] | None = None
    query: str | None = Field(default=None, max_length=180)
    filters: dict[str, str | int | float | bool | list[str] | None] | None = None
    products: list[dict[str, object]] | None = Field(default=None, max_length=8)

    @field_validator("name")
    @classmethod
    def nonempty_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Product name is required")
        return value.strip()

    @field_validator("specifications")
    @classmethod
    def bounded_specs(cls, value):
        import json
        if value is not None and (len(value) > 80 or len(json.dumps(value)) > 12000):
            raise ValueError("Specifications are too large")
        return value

    @field_validator("products")
    @classmethod
    def bounded_results(cls, value):
        import json
        if value is not None and len(json.dumps(value, ensure_ascii=False)) > 18000:
            raise ValueError("Listing results are too large")
        return value


class SuggestionRequest(BaseModel):
    product: SuggestionProduct


class SuggestionResponse(BaseModel):
    suggestions: list[Annotated[StrictStr, Field(min_length=10, max_length=240, pattern=r"\?$")]] = Field(min_length=3, max_length=4)

    @field_validator("suggestions")
    @classmethod
    def valid_questions(cls, values: list[str]) -> list[str]:
        questions = [" ".join(value.split()) for value in values]
        if any(not question.endswith("?") or len(question) > 240 or len(question) < 10 for question in questions):
            raise ValueError("Suggestions must be concise questions")
        if len({question.casefold() for question in questions}) != len(questions):
            raise ValueError("Suggestions must be unique")
        return questions
