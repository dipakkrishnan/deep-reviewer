import asyncio
import json
import logging
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from starlette.responses import StreamingResponse

from agent.config_models import AgentSettings, ReviewRequest
from agent.runtime import StreamSession, run_agent_streamed
from app_models import AnswerInput, ReviewInput, ReviewStarted
from prompts.orchestrator import ORCHESTRATOR_PROMPT
from telemetry import append_event, create_run, update_run
from utils import load_artifact
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger("deep-review")

# Note(Dipak): re-enable to use Anthropic API directly
load_dotenv()

app = FastAPI()

sessions: dict[str, StreamSession] = {}
UI_DIST = Path(__file__).parent / "ui" / "dist"


@app.post("/review", response_model=ReviewStarted)
async def start_review(body: ReviewInput):
    review_id = str(uuid.uuid4())
    log.info("Starting review %s source=%s mode=%s", review_id, body.source, body.mode)
    create_run(
        review_id,
        source=body.source,
        mode=body.mode,
        requested_model=body.model,
        requested_max_subagents=body.max_subagents,
        status="loading_artifact",
    )
    try:
        artifact = load_artifact(body.source)
    except FileNotFoundError as exc:
        update_run(review_id, status="failed", error=str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        update_run(review_id, status="failed", error=str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    settings = AgentSettings.from_request(
        ReviewRequest(
            mode=body.mode,
            model=body.model,
            max_subagents=body.max_subagents,
        )
    )

    system_prompt = ORCHESTRATOR_PROMPT.format(
        self_play_rounds=settings.self_play_rounds,
        subagent_count=settings.subagent_count,
    )

    session = StreamSession(
        review_id=review_id,
        events=asyncio.Queue(),
        answer_event=asyncio.Event(),
    )
    sessions[review_id] = session
    update_run(
        review_id,
        status="queued",
        artifact_title=artifact.title,
        artifact_source=artifact.source.value,
        artifact_url=artifact.url,
        model=settings.model,
        subagent_count=settings.subagent_count,
        self_play_rounds=settings.self_play_rounds,
        workspace=settings.workspace,
    )
    append_event(
        review_id,
        "review_started",
        artifact_title=artifact.title,
        subagent_count=settings.subagent_count,
        self_play_rounds=settings.self_play_rounds,
    )

    asyncio.create_task(
        run_agent_streamed(
            system_prompt=system_prompt,
            user_prompt=artifact.text,
            session=session,
            model=settings.model,
            cwd=settings.workspace,
        )
    )

    return ReviewStarted(review_id=review_id, title=artifact.title)


@app.get("/review/{review_id}/stream")
async def stream_review(review_id: str):
    if review_id not in sessions:
        raise HTTPException(status_code=404, detail="Review not found")

    log.info("Opening event stream for review %s", review_id)
    session = sessions[review_id]

    async def event_generator():
        try:
            while True:
                event = await session.events.get()
                append_event(review_id, "stream_event", payload=event)
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("type") in ("done", "error"):
                    break
        finally:
            update_run(review_id, stream_closed=True)
            sessions.pop(review_id, None)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/review/{review_id}/answer")
async def answer_questions(review_id: str, body: AnswerInput):
    if review_id not in sessions:
        raise HTTPException(status_code=404, detail="Review not found")

    log.info("Received answers for review %s", review_id)
    session = sessions[review_id]
    session.answer_slot = body.answers
    append_event(review_id, "answers_received", answers=body.answers)
    update_run(
        review_id,
        status="answers_received",
        answers=body.answers,
        answers_submitted=True,
    )
    await session.events.put({"type": "status", "status": "answers received"})
    session.answer_event.set()
    return {"status": "ok"}


if UI_DIST.exists():
    app.mount("/", StaticFiles(directory=UI_DIST, html=True), name="ui")
