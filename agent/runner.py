from pydantic import BaseModel

from agent.config_models import AgentSettings, ReviewRequest
from models import Artifact


class ReviewRunResult(BaseModel):
    """Structured result for a completed review run."""

    artifact_title: str
    settings: AgentSettings
    report_markdown: str


async def run_review(request: ReviewRequest, artifact: Artifact) -> ReviewRunResult:
    """Run a paper review and return a structured result."""
    settings = AgentSettings.from_request(request)
    raise NotImplementedError(
        f"Implement agent execution for {artifact.title!r} using {settings.model}."
    )
