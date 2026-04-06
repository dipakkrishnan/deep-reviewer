from pydantic import BaseModel, Field

from agent.config_models import ReviewMode


class ReviewInput(BaseModel):
    source: str
    filename: str | None = None
    mode: ReviewMode = ReviewMode.STANDARD
    model: str = "claude-opus-4-6"
    max_subagents: int | None = Field(default=None, ge=1)


class ReviewOutput(BaseModel):
    review: str
    title: str
    session_id: str | None


class ReviewStarted(BaseModel):
    review_id: str
    title: str


class AnswerInput(BaseModel):
    answers: dict[str, str]
