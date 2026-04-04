from enum import StrEnum

from pydantic import BaseModel, Field


class ReviewMode(StrEnum):
    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"


class ReviewPreset(BaseModel):
    """Typed execution defaults for a review mode."""

    mode: ReviewMode
    subagent_count: int = Field(gt=0)
    self_play_rounds: int = Field(gt=0)


REVIEW_PRESETS: dict[ReviewMode, ReviewPreset] = {
    ReviewMode.QUICK: ReviewPreset(
        mode=ReviewMode.QUICK,
        subagent_count=2,
        self_play_rounds=1,
    ),
    ReviewMode.STANDARD: ReviewPreset(
        mode=ReviewMode.STANDARD,
        subagent_count=4,
        self_play_rounds=1,
    ),
    ReviewMode.DEEP: ReviewPreset(
        mode=ReviewMode.DEEP,
        subagent_count=8,
        self_play_rounds=2,
    ),
}


def get_review_preset(mode: ReviewMode) -> ReviewPreset:
    return REVIEW_PRESETS[mode]


class ReviewRequest(BaseModel):
    """User-facing options for a review run."""

    mode: ReviewMode = ReviewMode.STANDARD
    model: str = "claude-opus-4-6"
    max_subagents: int | None = Field(default=None, ge=1)
    allowed_tools: list[str] = Field(default_factory=list)


class AgentSettings(BaseModel):
    """Resolved runtime settings used by the review orchestrator."""

    mode: ReviewMode
    model: str
    subagent_count: int = Field(gt=0)
    self_play_rounds: int = Field(gt=0)
    workspace: str = "/tmp/deep-review-workspace"

    @classmethod
    def from_request(cls, request: ReviewRequest) -> "AgentSettings":
        preset = get_review_preset(request.mode)
        return cls(
            mode=request.mode,
            model=request.model,
            subagent_count=request.max_subagents or preset.subagent_count,
            self_play_rounds=preset.self_play_rounds,
        )
