# Deep Review

AI generates artifacts faster than humans can verify them. The bottleneck has shifted from writing to reviewing — catching errors in AI-drafted papers, proofs, and analyses requires domain expertise that's expensive and slow to acquire. Each pass surfaces new issues, and multiple rounds of manual review pile up before an artifact is publishable.

Deep Review reduces that edit volume. Upload a paper, answer a short calibration interview, and get back an expert-grade review that finds flaws — both obvious and opaque — so you fix more in fewer passes than manual review or a generic ChatGPT conversation with file upload.

The system spawns domain-specific subagents (theorem checkers, literature searchers, methods reviewers), runs adversarial self-critique, and produces a structured review with severity-ranked findings traced to exact locations in the paper.

## Stack

- **Backend**: FastAPI + Claude Agent SDK, traced via Braintrust
- **Frontend**: Vite SPA served from the same container
- **Infra**: Docker → Artifact Registry → Cloud Run, deployed on push to `main`

## Local dev

```bash
uv sync
cp .env.example .env  # fill in keys below
uv run uvicorn app:app --reload
```

UI (separate terminal):
```bash
cd ui && npm install && npm run dev
```

## Environment variables

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API access |
| `BRAINTRUST_API_KEY` | Tracing and evals |
| `DEEP_REVIEW_SECRET` | Shared secret for API auth |
| `POSTHOG_API_KEY` | Usage analytics |
