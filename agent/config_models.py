from enum import StrEnum
from typing import Literal

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
    def from_request(cls, request: ReviewRequest, review_id: str) -> "AgentSettings":
        preset = get_review_preset(request.mode)
        return cls(
            mode=request.mode,
            model=request.model,
            subagent_count=request.max_subagents or preset.subagent_count,
            self_play_rounds=preset.self_play_rounds,
            workspace=f"/tmp/deep-review-workspace/{review_id}",
        )


class ReviewPackageEntry(BaseModel):
    """Provisional schema for user-facing work product exports."""

    key: str
    label: str
    source: Literal["report", "session", "workspace"]
    path: str
    description: str | None = None
    include_by_default: bool = True
    workspace_globs: list[str] = Field(default_factory=list)


class ReviewPackageConfig(BaseModel):
    """
    Sketch of the review package contract.

    This is intentionally still being iterated on. The goal is to keep a stable
    user-facing export shape even as the internal session workspace evolves.
    """

    version: str = "v1alpha"
    archive_label: str = "work-product"
    entries: list[ReviewPackageEntry]


DEFAULT_REVIEW_PACKAGE = ReviewPackageConfig(
    entries=[
        ReviewPackageEntry(
            key="report",
            label="Final review",
            source="report",
            path="report.md",
            description="The final markdown review shown in the app.",
        ),
        ReviewPackageEntry(
            key="verification",
            label="Verification files",
            source="workspace",
            path="verification",
            description="Selected scripts and generated files from the review workspace.",
            workspace_globs=["*.py", "*.ipynb", "*.txt", "*.csv", "*.json", "*.md"],
        ),
    ]
)
