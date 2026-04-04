import asyncio
import json
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from starlette.responses import StreamingResponse

from agent.config_models import AgentSettings, ReviewRequest
from agent.runtime import StreamSession, run_agent_streamed
from app_models import AnswerInput, ReviewInput, ReviewStarted
from prompts.orchestrator import ORCHESTRATOR_PROMPT
from utils import load_artifact

app = FastAPI()

sessions: dict[str, StreamSession] = {}
UI_DIST = Path(__file__).parent / "ui" / "dist"


@app.post("/review", response_model=ReviewStarted)
async def start_review(body: ReviewInput):
    try:
        artifact = load_artifact(body.source)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

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

    review_id = str(uuid.uuid4())
    session = StreamSession(
        events=asyncio.Queue(),
        answer_event=asyncio.Event(),
    )
    sessions[review_id] = session

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

    session = sessions[review_id]

    async def event_generator():
        try:
            while True:
                event = await session.events.get()
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("type") in ("done", "error"):
                    break
        finally:
            sessions.pop(review_id, None)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/review/{review_id}/answer")
async def answer_questions(review_id: str, body: AnswerInput):
    if review_id not in sessions:
        raise HTTPException(status_code=404, detail="Review not found")

    session = sessions[review_id]
    session.answer_slot = body.answers
    await session.events.put({"type": "status", "status": "answers received"})
    session.answer_event.set()
    return {"status": "ok"}


if UI_DIST.exists():
    app.mount("/", StaticFiles(directory=UI_DIST, html=True), name="ui")
