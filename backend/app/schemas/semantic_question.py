"""Natural-language questions constrained to the semantic query catalog."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, StringConstraints


class SemanticQuestionRequest(BaseModel):
    """One newsroom question submitted by an SID."""

    question: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)
    ]


class SemanticQuestionAnswerRead(BaseModel):
    """A grounded answer or an explicit out-of-catalog response."""

    status: Literal["answered", "unanswerable"]
    question: str
    answer: str
    query_id: str | None = None
    query: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    model: str
    prompt_version: str
