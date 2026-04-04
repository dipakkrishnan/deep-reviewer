# UI

Minimal TypeScript frontend for the Deep Review task interface.

## Run

1. `cd ui`
2. `npm install`
3. `npm run dev`

The UI uses the backend contract exposed by [`app.py`](/Users/dipakkrishnan/git/clones/deep-review/app.py):

- `POST /review`
- `GET /review/{review_id}/stream`
- `POST /review/{review_id}/answer`

In development, Vite proxies `/review` to `http://127.0.0.1:8000` via [`ui/vite.config.ts`](/Users/dipakkrishnan/git/clones/deep-review/ui/vite.config.ts).

## Production build

1. `cd ui`
2. `npm install`
3. `npm run build`
4. run the FastAPI app

If `ui/dist` exists, [`app.py`](/Users/dipakkrishnan/git/clones/deep-review/app.py) serves the built frontend directly.

## Notes

- The UI is intentionally single-task: launch review, answer interview, wait, inspect final artifact.
- The launch form accepts either a local PDF path or an arXiv URL, matching [`load_artifact`](/Users/dipakkrishnan/git/clones/deep-review/utils.py).
- When the backend is available, the interface starts a run, listens for `AskUserQuestion` via SSE, posts answers, and renders the final review.
