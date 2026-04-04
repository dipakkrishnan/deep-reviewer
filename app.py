from fastapi import FastAPI

from agent.config_models import AgentSettings, ReviewRequest
from agent.runtime import run_agent
from app_models import ReviewInput, ReviewOutput
from prompts.orchestrator import ORCHESTRATOR_PROMPT
from utils import load_artifact

app = FastAPI()


@app.post("/review", response_model=ReviewOutput)
async def review(body: ReviewInput):
    artifact = load_artifact(body.source)

    settings = AgentSettings.from_request(
        ReviewRequest(
            mode=body.mode,
            model=body.model,
            max_subagents=body.max_subagents,
        )
    )

    system_prompt = ORCHESTRATOR_PROMPT.format(
        self_play_rounds=settings.self_play_rounds
    )

    result = await run_agent(
        system_prompt=system_prompt,
        user_prompt=artifact.text,
        model=settings.model,
        cwd=settings.workspace,
    )

    return ReviewOutput(
        review=result.text,
        title=artifact.title,
        session_id=result.session_id,
    )
