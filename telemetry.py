import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import posthog

_POSTHOG_KEY = os.getenv("POSTHOG_API_KEY")
if _POSTHOG_KEY:
    posthog.api_key = _POSTHOG_KEY
    posthog.host = "https://us.i.posthog.com"

log = logging.getLogger("deep-review")

RUNS_DIR = Path("review_runs")


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def capture(event: str, review_id: str, **properties: Any) -> None:
    if not _POSTHOG_KEY:
        return
    posthog.capture(distinct_id=review_id, event=event, properties=properties)


def _run_path(review_id: str) -> Path:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    return RUNS_DIR / f"{review_id}.json"


def _load_run(review_id: str) -> dict[str, Any]:
    path = _run_path(review_id)
    if not path.exists():
        return {"review_id": review_id, "events": []}
    return json.loads(path.read_text())


def _write_run(review_id: str, payload: dict[str, Any]) -> None:
    _run_path(review_id).write_text(json.dumps(payload, indent=2, sort_keys=True))


def write_artifact(review_id: str, content: str) -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    (RUNS_DIR / f"{review_id}.md").write_text(content)


def create_run(review_id: str, **fields: Any) -> None:
    payload = {
        "review_id": review_id,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "events": [],
        **fields,
    }
    _write_run(review_id, payload)


def update_run(review_id: str, **fields: Any) -> None:
    payload = _load_run(review_id)
    payload.update(fields)
    payload["updated_at"] = _now_iso()
    _write_run(review_id, payload)


def append_event(review_id: str, event_type: str, **fields: Any) -> None:
    payload = _load_run(review_id)
    events = payload.setdefault("events", [])
    events.append(
        {
            "type": event_type,
            "timestamp": _now_iso(),
            **fields,
        }
    )
    payload["updated_at"] = _now_iso()
    _write_run(review_id, payload)
