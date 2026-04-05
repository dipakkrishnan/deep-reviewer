import asyncio
import logging
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, SystemMessage, query
from claude_agent_sdk.types import (
    AssistantMessage,
    HookMatcher,
    PermissionResultAllow,
    PermissionResultDeny,
    TaskProgressMessage,
    TaskStartedMessage,
    ToolPermissionContext,
    ToolUseBlock,
)

log = logging.getLogger("deep-review")

from agent.claude_tools import ORCHESTRATOR_TOOLS
from telemetry import append_event, update_run

AskUserHandler = Callable[[dict], dict[str, str]]


def _sdk_stderr(line: str) -> None:
    log.error("Claude CLI stderr: %s", line.rstrip())


def _build_can_use_tool(ask_user: AskUserHandler | None):
    """Return a can_use_tool callback that routes AskUserQuestion to the caller."""

    async def can_use_tool(
        tool_name: str, input_data: dict, context: ToolPermissionContext
    ) -> PermissionResultAllow | PermissionResultDeny:
        if tool_name == "AskUserQuestion":
            if ask_user is None:
                log.warning("AskUserQuestion fired but no handler provided")
                return PermissionResultDeny(message="No user input handler provided.")
            log.info("Agent is asking the user clarifying questions")
            answers = ask_user(input_data)
            log.info("User answered %d question(s)", len(answers))
            return PermissionResultAllow(
                updated_input={
                    "questions": input_data.get("questions", []),
                    "answers": answers,
                }
            )
        log.debug("Auto-approved tool: %s", tool_name)
        return PermissionResultAllow(updated_input=input_data)

    return can_use_tool


async def _dummy_hook(input_data, tool_use_id, context):
    return {"continue_": True}


@dataclass
class AgentResult:
    text: str
    session_id: str | None


async def run_agent(
    system_prompt: str,
    user_prompt: str,
    model: str = "claude-opus-4-6",
    cwd: str | None = None,
    provider: str = "anthropic",
    session_id: str | None = None,
    ask_user: AskUserHandler | None = None,
) -> AgentResult:
    """Run a prompt through the Claude Agent SDK and return the result."""
    log.info("Starting review — model=%s provider=%s resume=%s", model, provider, session_id)
    if provider == "anthropic":
        if cwd:
            Path(cwd).mkdir(parents=True, exist_ok=True)
        options = ClaudeAgentOptions(
            allowed_tools=ORCHESTRATOR_TOOLS,
            permission_mode="bypassPermissions",
            system_prompt=system_prompt,
            model=model,
            cwd=cwd,
            resume=session_id,
            can_use_tool=_build_can_use_tool(ask_user),
            stderr=_sdk_stderr,
            debug_stderr=sys.stderr,
            hooks={
                "PreToolUse": [HookMatcher(matcher=None, hooks=[_dummy_hook])]
            },
        )
        async def prompt_stream():
            yield {
                "type": "user",
                "message": {"role": "user", "content": user_prompt},
            }

        log.info("Agent loop starting")
        result_text = ""
        captured_session_id = session_id
        async for message in query(prompt=prompt_stream(), options=options):
            if isinstance(message, SystemMessage) and message.subtype == "init":
                captured_session_id = message.data.get("session_id")
                log.info("Session established: %s", captured_session_id)
            if isinstance(message, ResultMessage):
                result_text = message.result
                log.info("Agent finished — result length=%d chars", len(result_text))
        return AgentResult(text=result_text, session_id=captured_session_id)

    raise NotImplementedError(f"Unsupported provider: {provider}")


@dataclass
class StreamSession:
    """Shared state for pause/resume coordination during streamed runs."""

    review_id: str
    events: asyncio.Queue
    answer_event: asyncio.Event
    answer_slot: dict | None = None


def _build_can_use_tool_streamed(session: StreamSession):
    """Return a can_use_tool callback that streams questions and waits for answers."""

    async def can_use_tool(
        tool_name: str, input_data: dict, context: ToolPermissionContext
    ) -> PermissionResultAllow | PermissionResultDeny:
        if tool_name == "AskUserQuestion":
            questions = input_data.get("questions", [])
            log.info("Agent asking %d question(s), pausing for user", len(questions))
            append_event(
                session.review_id,
                "questions_requested",
                question_count=len(questions),
                questions=questions,
            )
            update_run(
                session.review_id,
                status="waiting_for_answers",
                question_count=len(questions),
            )
            await session.events.put(
                {"type": "status", "status": "waiting for interview answers"}
            )
            await session.events.put({"type": "questions", "questions": questions})
            await session.answer_event.wait()
            session.answer_event.clear()
            answers = session.answer_slot or {}
            session.answer_slot = None
            log.info("User answered, resuming agent")
            append_event(
                session.review_id,
                "answers_applied",
                answers=answers,
            )
            update_run(
                session.review_id,
                status="resuming_after_answers",
                answers=answers,
                answers_submitted=True,
            )
            await session.events.put(
                {"type": "status", "status": "interview complete, resuming review"}
            )
            return PermissionResultAllow(
                updated_input={"questions": questions, "answers": answers}
            )
        return PermissionResultAllow(updated_input=input_data)

    return can_use_tool


def _summarize_tool_input(name: str, input_data: dict) -> str:
    """Return a short human-readable preview of what a tool call is doing."""
    if name == "WebSearch":
        return input_data.get("query", name)
    if name == "WebFetch":
        return input_data.get("url", name)
    if name == "Read":
        return input_data.get("file_path", name)
    if name == "Agent":
        prompt = input_data.get("prompt", "")
        return prompt[:80] + ("..." if len(prompt) > 80 else "")
    return name


async def run_agent_streamed(
    system_prompt: str,
    user_prompt: str,
    session: StreamSession,
    model: str = "claude-opus-4-6",
    cwd: str | None = None,
    provider: str = "anthropic",
) -> None:
    """Run a prompt through the Claude Agent SDK, pushing events to session.events."""
    log.info("Starting streamed review — model=%s provider=%s", model, provider)
    append_event(
        session.review_id,
        "agent_started",
        model=model,
        provider=provider,
        cwd=cwd,
    )
    update_run(
        session.review_id,
        status="running",
        model=model,
        provider=provider,
        workspace=cwd,
    )
    if provider != "anthropic":
        await session.events.put(
            {"type": "error", "message": f"Unsupported provider: {provider}"}
        )
        await session.events.put({"type": "done"})
        return

    try:
        result_emitted = False
        if cwd:
            Path(cwd).mkdir(parents=True, exist_ok=True)
        options = ClaudeAgentOptions(
            allowed_tools=ORCHESTRATOR_TOOLS,
            permission_mode="bypassPermissions",
            system_prompt=system_prompt,
            model=model,
            cwd=cwd,
            can_use_tool=_build_can_use_tool_streamed(session),
            stderr=_sdk_stderr,
            debug_stderr=sys.stderr,
            hooks={
                "PreToolUse": [HookMatcher(matcher=None, hooks=[_dummy_hook])]
            },
        )

        async def prompt_stream():
            yield {
                "type": "user",
                "message": {"role": "user", "content": user_prompt},
            }

        await session.events.put({"type": "status", "status": "running"})
        async for message in query(prompt=prompt_stream(), options=options):
            if isinstance(message, SystemMessage) and message.subtype == "init":
                sid = message.data.get("session_id")
                log.info("Session established: %s", sid)
                append_event(session.review_id, "session_established", session_id=sid)
                update_run(session.review_id, session_id=sid)
                await session.events.put(
                    {"type": "status", "status": "running", "session_id": sid}
                )
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, ToolUseBlock):
                        await session.events.put({
                            "type": "progress",
                            "tool": block.name,
                            "input_preview": _summarize_tool_input(block.name, block.input),
                        })
            if isinstance(message, TaskStartedMessage):
                await session.events.put({
                    "type": "progress",
                    "tool": "Agent",
                    "input_preview": message.description,
                })
            if isinstance(message, TaskProgressMessage):
                await session.events.put({
                    "type": "progress",
                    "tool": message.last_tool_name or "Agent",
                    "input_preview": message.description,
                })
            if isinstance(message, ResultMessage):
                log.info("Agent finished — result length=%d chars", len(message.result))
                result_emitted = True
                append_event(
                    session.review_id,
                    "agent_finished",
                    session_id=message.session_id,
                    total_cost_usd=message.total_cost_usd,
                    duration_ms=message.duration_ms,
                    num_turns=message.num_turns,
                    usage=message.usage,
                    model_usage=message.model_usage,
                    is_error=message.is_error,
                )
                update_run(
                    session.review_id,
                    status="completed" if not message.is_error else "failed",
                    session_id=message.session_id,
                    total_cost_usd=message.total_cost_usd,
                    duration_ms=message.duration_ms,
                    duration_api_ms=message.duration_api_ms,
                    num_turns=message.num_turns,
                    usage=message.usage,
                    model_usage=message.model_usage,
                    stop_reason=message.stop_reason,
                    result_preview=(message.result or "")[:500],
                    error_messages=message.errors,
                )
                await session.events.put(
                    {"type": "status", "status": "final review ready"}
                )
                await session.events.put({"type": "result", "text": message.result})
                break
    except Exception as exc:
        if result_emitted:
            log.warning(
                "Claude transport failed after final result was emitted; treating run as completed"
            )
            append_event(
                session.review_id,
                "post_result_transport_error",
                error=str(exc),
            )
            return
        log.exception("Agent loop failed")
        append_event(session.review_id, "agent_failed", error=str(exc))
        update_run(session.review_id, status="failed", error=str(exc))
        await session.events.put({"type": "error", "message": str(exc)})
    finally:
        await session.events.put({"type": "done"})
