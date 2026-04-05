import katex from "katex";
import "katex/dist/katex.min.css";
import "./styles.css";

type ReviewMode = "quick" | "standard" | "deep";
type Stage = "ready" | "interview" | "running" | "complete";

type Question = {
  question: string;
  options?: Array<{ label: string; description: string }>;
};

type StreamEvent =
  | { type: "status"; status?: string; session_id?: string }
  | { type: "questions"; questions?: Question[] }
  | { type: "progress"; tool?: string; input_preview?: string }
  | { type: "result"; text?: string }
  | { type: "error"; message?: string }
  | { type: "done" };

type AppState = {
  stage: Stage;
  reviewId: string | null;
  sessionId: string | null;
  title: string;
  statusText: string;
  source: string;
  mode: ReviewMode;
  questions: Question[];
  answers: Record<string, string>;
  resultText: string;
  progress: Array<{ tool: string; detail: string }>;
  log: string[];
};

const state: AppState = {
  stage: "ready",
  reviewId: null,
  sessionId: null,
  title: "Deep Review",
  statusText: "Ready to launch a review.",
  source: "./paper_clean_final.pdf",
  mode: "standard",
  questions: [],
  answers: {},
  resultText: "",
  progress: [],
  log: [
    "Upload a paper, start the task, answer the interview, and wait for the final review artifact."
  ]
};

let stream: EventSource | null = null;

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function markdownToHtml(text: string): string {
  const blocks = text.trim().split(/\n{2,}/).filter(Boolean);
  return blocks
    .map((block) => renderBlock(block.trim()))
    .join("");
}

function renderBlock(block: string): string {
  if (/^---+$/.test(block)) {
    return "<hr />";
  }

  if (block.startsWith("$$") && block.endsWith("$$")) {
    return renderMath(block.slice(2, -2).trim(), true);
  }

  const lines = block.split("\n");
  if (lines.every((line) => /^\d+\.\s+/.test(line))) {
    const items = lines
      .map((line) => line.replace(/^\d+\.\s+/, ""))
      .map((line) => `<li>${renderInline(line)}</li>`)
      .join("");
    return `<ol>${items}</ol>`;
  }

  if (lines.every((line) => /^-\s+/.test(line))) {
    const items = lines
      .map((line) => line.replace(/^-\s+/, ""))
      .map((line) => `<li>${renderInline(line)}</li>`)
      .join("");
    return `<ul>${items}</ul>`;
  }

  if (block.startsWith("### ")) {
    return `<h3>${renderInline(block.slice(4))}</h3>`;
  }

  if (block.startsWith("## ")) {
    return `<h2>${renderInline(block.slice(3))}</h2>`;
  }

  if (block.startsWith("# ")) {
    return `<h1>${renderInline(block.slice(2))}</h1>`;
  }

  const html = lines.map((line) => renderInline(line)).join("<br />");
  return `<p>${html}</p>`;
}

function renderMath(tex: string, displayMode: boolean): string {
  try {
    return katex.renderToString(tex, { displayMode, throwOnError: false });
  } catch {
    return `<code>${escapeHtml(tex)}</code>`;
  }
}

function renderInline(text: string): string {
  // Pull out $...$ math spans before escaping, render them with KaTeX
  return escapeHtml(text)
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\$((?:[^$\\]|\\.)+)\$/g, (_, tex) => renderMath(unescapeHtml(tex), false));
}

function unescapeHtml(value: string): string {
  return value
    .replaceAll("&amp;", "&")
    .replaceAll("&lt;", "<")
    .replaceAll("&gt;", ">");
}

function render(): void {
  const app = document.querySelector<HTMLDivElement>("#app");
  if (!app) return;

  app.innerHTML = `
    <div class="shell">
      <div class="backdrop backdrop-a"></div>
      <div class="backdrop backdrop-b"></div>

      <header class="hero">
        <p class="eyebrow">Deep Review</p>
        <h1>Expert review, without the clutter.</h1>
        <p class="lede">Upload a paper, answer a short interview, and receive a careful review artifact shaped to the task.</p>
      </header>

      <main class="task-layout">
        <section class="task-panel glass">
          <div class="task-head">
            <div>
              <p class="panel-kicker">Task</p>
              <h2>${escapeHtml(prettifyTitle(state.title))}</h2>
            </div>
            <div class="status-chip">${escapeHtml(state.statusText)}</div>
          </div>

          ${renderTaskBody()}
        </section>

        <section class="meta-panel glass">
          <div class="panel-head">
            <p class="panel-kicker">Run</p>
            <h3>Session</h3>
          </div>
          <dl class="meta-list">
            <div><dt>Review ID</dt><dd>${escapeHtml(state.reviewId ?? "pending")}</dd></div>
            <div><dt>Session</dt><dd>${escapeHtml(state.sessionId ?? "pending")}</dd></div>
            <div><dt>Depth</dt><dd>${escapeHtml(readableMode(state.mode))}</dd></div>
          </dl>
          <div class="panel-head panel-head-secondary">
            <p class="panel-kicker">Activity</p>
            <h3>Log</h3>
          </div>
          <ul class="log-list">
            ${state.log.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
          </ul>
        </section>
      </main>
    </div>
  `;

  bindEvents();
}

function renderTaskBody(): string {
  if (state.stage === "ready") {
    return `
      <div class="body-block">
        <div class="setup-grid">
          <label class="field">
            <span>Paper path or arXiv URL</span>
            <input id="source" value="${escapeHtml(state.source)}" placeholder="/path/to/paper.pdf or https://arxiv.org/abs/..." />
          </label>
          <label class="field">
            <span>Review depth</span>
            <select id="mode">
              ${[
                { value: "quick", label: "Quick scan" },
                { value: "standard", label: "Standard review" },
                { value: "deep", label: "Deep review" }
              ]
                .map(
                  ({ value, label }) =>
                    `<option value="${value}" ${state.mode === value ? "selected" : ""}>${label}</option>`
                )
                .join("")}
            </select>
          </label>
          <label class="field">
            <span>Intensity</span>
            <p class="field-note">${escapeHtml(intensityCopy(state.mode))}</p>
          </label>
        </div>
        <div class="action-row">
          <button class="primary" id="start-review">Start Review</button>
        </div>
      </div>
    `;
  }

  if (state.stage === "interview") {
    return `
      <form class="body-block interview-form" id="answer-form">
        <div class="section-intro">
          <p class="panel-kicker">Interview</p>
          <h3>Answer the calibration questions</h3>
          <p>The system has paused at the interview stage. Submit answers to resume the review task.</p>
        </div>
        ${state.questions
          .map((question, index) => {
            const options = question.options ?? [];
            return `
              <section class="question-card">
                <div class="question-prompt">${index + 1}. ${escapeHtml(question.question)}</div>
                ${options
                  .map(
                    (option) => `
                      <label class="option-row">
                        <input type="radio" name="q-${index}" value="${escapeHtml(option.label)}" />
                        <span>
                          <strong>${escapeHtml(option.label)}</strong>
                          <small>${escapeHtml(option.description)}</small>
                        </span>
                      </label>
                    `
                  )
                  .join("")}
                <label class="field">
                  <span>Custom answer</span>
                  <input name="custom-${index}" placeholder="Optional" />
                </label>
              </section>
            `;
          })
          .join("")}
        <div class="action-row">
          <button class="primary" type="submit">Submit Answers</button>
        </div>
      </form>
    `;
  }

  if (state.stage === "running") {
    const feedItems = state.progress
      .map(
        (p) =>
          `<li><span class="feed-tool">${escapeHtml(p.tool)}</span> ${escapeHtml(p.detail)}</li>`
      )
      .join("");

    return `
      <div class="body-block run-block">
        <div class="section-intro">
          <p class="panel-kicker">In Progress</p>
          <h3>Review underway</h3>
        </div>
        <div class="progress-card">
          <div class="pulse"></div>
          <strong>${escapeHtml(state.statusText)}</strong>
        </div>
        ${feedItems ? `<ul class="progress-feed">${feedItems}</ul>` : ""}
      </div>
    `;
  }

  return `
    <div class="body-block result-block">
      <div class="section-intro">
        <p class="panel-kicker">Artifact</p>
        <h3>Final review</h3>
        <p>The task is complete. This is the current review artifact returned by the backend.</p>
      </div>
      <article class="report">
        ${state.resultText ? markdownToHtml(state.resultText) : "<p>No final artifact received yet.</p>"}
      </article>
    </div>
  `;
}

function bindEvents(): void {
  const source = document.querySelector<HTMLInputElement>("#source");
  source?.addEventListener("change", () => {
    state.source = source.value.trim();
  });

  const mode = document.querySelector<HTMLSelectElement>("#mode");
  mode?.addEventListener("change", () => {
    state.mode = mode.value as ReviewMode;
    render();
  });

  document.querySelector<HTMLButtonElement>("#start-review")?.addEventListener("click", startReview);
  document.querySelector<HTMLFormElement>("#answer-form")?.addEventListener("submit", submitAnswers);
}

async function startReview(): Promise<void> {
  closeStream();
  state.stage = "running";
  state.statusText = "Launching review run...";
  state.resultText = "";
  state.progress = [];
  state.reviewId = null;
  state.sessionId = null;
  state.log.unshift(`Submitting artifact: ${state.source}`);
  render();

  try {
    const response = await fetch("/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source: state.source,
        mode: state.mode,
        max_subagents: null
      })
    });

    if (!response.ok) {
      throw new Error(await readErrorMessage(response, "Review start failed"));
    }

    const data = (await response.json()) as { review_id: string; title: string };
    state.reviewId = data.review_id;
    state.title = data.title;
    state.statusText = "Review started. Waiting for stream.";
    state.log.unshift(`Review started: ${data.review_id}`);
    openStream(data.review_id);
    render();
  } catch (error) {
    state.stage = "ready";
    state.statusText = "Could not reach backend.";
    state.log.unshift(error instanceof Error ? error.message : "Unknown launch error");
    render();
  }
}

function openStream(reviewId: string): void {
  closeStream();
  stream = new EventSource(`/review/${reviewId}/stream`);

  stream.onmessage = (event) => {
    handleEvent(JSON.parse(event.data) as StreamEvent);
  };

  stream.onerror = () => {
    state.log.unshift("Stream disconnected.");
    closeStream();
    render();
  };
}

function handleEvent(event: StreamEvent): void {
  if (event.type === "status") {
    state.statusText = event.status ?? "running";
    if (event.session_id) {
      state.sessionId = event.session_id;
    }
    state.log.unshift(`Status: ${state.statusText}`);
  }

  if (event.type === "progress") {
    const entry = { tool: event.tool ?? "Agent", detail: event.input_preview ?? "" };
    state.progress.unshift(entry);
    if (state.progress.length > 30) state.progress.length = 30;
  }

  if (event.type === "questions") {
    state.questions = event.questions ?? [];
    state.answers = {};
    state.stage = "interview";
    state.statusText = "Interview waiting on answers.";
    state.log.unshift("AskUserQuestion received from backend.");
  }

  if (event.type === "result") {
    state.resultText = event.text ?? "";
    state.stage = "complete";
    state.statusText = "Review complete.";
    state.log.unshift("Final review artifact received.");
  }

  if (event.type === "error") {
    state.stage = "ready";
    state.statusText = "Run failed.";
    state.log.unshift(event.message ?? "Unknown backend error");
  }

  render();
}

async function submitAnswers(event: SubmitEvent): Promise<void> {
  event.preventDefault();
  if (!state.reviewId) {
    state.log.unshift("No active review found for answer submission.");
    render();
    return;
  }

  const form = event.currentTarget as HTMLFormElement;
  const formData = new FormData(form);
  const answers: Record<string, string> = {};

  state.questions.forEach((question, index) => {
    const selected = formData.get(`q-${index}`)?.toString().trim() ?? "";
    const custom = formData.get(`custom-${index}`)?.toString().trim() ?? "";
    answers[question.question] = custom || selected;
  });

  state.answers = answers;
  state.stage = "running";
  state.statusText = "Submitting interview answers...";
  state.log.unshift("Interview answers submitted.");
  render();

  try {
    const response = await fetch(`/review/${state.reviewId}/answer`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answers })
    });

    if (!response.ok) {
      throw new Error(await readErrorMessage(response, "Answer submit failed"));
    }
  } catch (error) {
    state.stage = "interview";
    state.statusText = "Answer submission failed.";
    state.log.unshift(error instanceof Error ? error.message : "Unknown answer error");
    render();
  }
}

function closeStream(): void {
  stream?.close();
  stream = null;
}

function readableMode(mode: ReviewMode): string {
  if (mode === "quick") return "Quick scan";
  if (mode === "deep") return "Deep review";
  return "Standard review";
}

function prettifyTitle(title: string): string {
  const cleaned = title
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (!cleaned) {
    return "Deep Review";
  }
  return cleaned.replace(/\b\w/g, (match) => match.toUpperCase());
}

function intensityCopy(mode: ReviewMode): string {
  if (mode === "quick") {
    return "Fastest pass. Best for early drafts and obvious weaknesses.";
  }
  if (mode === "deep") {
    return "Highest scrutiny. Broader search, stronger adversarial checking, slower turnaround.";
  }
  return "Balanced depth. Strong default for most serious paper reviews.";
}

async function readErrorMessage(response: Response, fallback: string): Promise<string> {
  const text = await response.text();
  if (!text) {
    return `${fallback}: ${response.status}`;
  }
  try {
    const parsed = JSON.parse(text) as { detail?: string };
    if (parsed.detail) {
      return parsed.detail;
    }
  } catch {
    // Ignore JSON parsing failures and fall back to raw text.
  }
  return `${fallback}: ${text}`;
}

render();
