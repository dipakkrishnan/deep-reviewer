from pydantic import BaseModel, Field

from agent.config_models import ReviewMode


class ReviewInput(BaseModel):
    source: str
    mode: ReviewMode = ReviewMode.STANDARD
    model: str = "claude-opus-4-6"
    max_subagents: int | None = Field(default=None, ge=1)


class ReviewOutput(BaseModel):
    review: str
    title: str
    session_id: str | None
