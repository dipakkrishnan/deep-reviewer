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
  accessKey: string | null;
  authChecked: boolean;
  authRequired: boolean;
  stage: Stage;
  reviewId: string | null;
  sessionId: string | null;
  title: string;
  statusText: string;
  sourceInput: string;
  uploadedSource: string | null;
  mode: ReviewMode;
  questions: Question[];
  answers: Record<string, string>;
  resultText: string;
  progress: Array<{ tool: string; detail: string }>;
  uploadedFilename: string | null;
};

const state: AppState = {
  accessKey: sessionStorage.getItem("deep-review-access-key"),
  authChecked: false,
  authRequired: false,
  stage: "ready",
  reviewId: null,
  sessionId: null,
  title: "Deep Review",
  statusText: "Ready to launch a review.",
  sourceInput: "",
  uploadedSource: null,
  mode: "standard",
  questions: [],
  answers: {},
  resultText: "",
  progress: [],
  uploadedFilename: null,
};

let stream: EventSource | null = null;
const ACCESS_KEY_STORAGE = "deep-review-access-key";

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function markdownToHtml(text: string): string {
  const blocks = tokenizeBlocks(text);
  return blocks.map((block) => renderBlock(block)).join("");
}

function tokenizeBlocks(text: string): string[] {
  const normalized = text.replace(/\r\n/g, "\n").trim();
  if (!normalized) {
    return [];
  }

  const blocks: string[] = [];
  const lines = normalized.split("\n");
  let buffer: string[] = [];
  let inDisplayMath = false;
  let mathBuffer: string[] = [];

  const flushBuffer = () => {
    const joined = buffer.join("\n").trim();
    if (joined) {
      blocks.push(joined);
    }
    buffer = [];
  };

  const flushMath = () => {
    const joined = mathBuffer.join("\n").trim();
    if (joined) {
      blocks.push(`$$\n${joined}\n$$`);
    }
    mathBuffer = [];
  };

  for (const line of lines) {
    const trimmed = line.trim();

    if (trimmed === "$$") {
      if (inDisplayMath) {
        flushMath();
        inDisplayMath = false;
      } else {
        flushBuffer();
        inDisplayMath = true;
      }
      continue;
    }

    if (inDisplayMath) {
      mathBuffer.push(line);
      continue;
    }

    if (!trimmed) {
      flushBuffer();
      continue;
    }

    buffer.push(line);
  }

  flushBuffer();
  if (inDisplayMath) {
    flushMath();
  }

  return blocks;
}

function renderBlock(block: string): string {
  if (/^---+$/.test(block)) {
    return "<hr />";
  }

  if (block.startsWith("$$") && block.endsWith("$$")) {
    return renderMath(
      block
        .replace(/^\$\$\s*/, "")
        .replace(/\s*\$\$$/, "")
        .trim(),
      true
    );
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

  if (!state.authChecked) {
    app.innerHTML = `
      <div class="shell shell-auth">
        <div class="backdrop backdrop-a"></div>
        <div class="backdrop backdrop-b"></div>

        <main class="auth-layout">
          <section class="auth-card glass">
            <p class="eyebrow">Deep Review</p>
            <h1>Loading</h1>
            <p class="auth-copy">Checking access requirements.</p>
          </section>
        </main>
      </div>
    `;
    return;
  }

  if (state.authRequired && !state.accessKey) {
    app.innerHTML = `
      <div class="shell shell-auth">
        <div class="backdrop backdrop-a"></div>
        <div class="backdrop backdrop-b"></div>

        <main class="auth-layout">
          <section class="auth-card glass">
            <p class="eyebrow">Deep Review</p>
            <h1>Enter access key</h1>
            <form class="auth-form" id="auth-form">
              <label class="field">
                <span>Access key</span>
                <input id="access-key" name="access-key" type="password" autocomplete="current-password" autofocus />
              </label>
              <div class="action-row action-row-inline">
                <button class="primary" type="submit">Continue</button>
              </div>
            </form>
          </section>
        </main>
      </div>
    `;
    bindEvents();
    return;
  }

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
            <div class="task-head-controls">
              ${state.stage === "ready"
                ? `
                  <label class="field field-depth field-head">
                    <span class="field-label-row">
                      <span>Review depth</span>
                      <button
                        type="button"
                        class="info-trigger"
                        aria-label="Explain review depth"
                        aria-describedby="mode-help"
                      >?</button>
                    </span>
                    <div class="select-shell">
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
                    </div>
                    <span class="tooltip-bubble" id="mode-help" role="tooltip">${escapeHtml(intensityCopy(state.mode))}</span>
                  </label>
                `
                : ""}
              <div class="status-chip">${escapeHtml(state.statusText)}</div>
            </div>
          </div>

          ${renderTaskBody()}
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
        <section class="artifact-card artifact-card-simple">
          <div class="section-intro section-intro-tight">
            <p class="panel-kicker">Artifact</p>
            <h3>Upload the paper</h3>
          </div>

          <div class="field field-paper">
            <div class="drop-zone" id="drop-zone">
              <input type="file" id="file-input" accept=".pdf" hidden />
              ${state.uploadedFilename
                ? `<p class="drop-label">✓ ${escapeHtml(state.uploadedFilename)}</p>`
                : `<p class="drop-label">Drop a PDF here or <button type="button" class="link-btn" id="pick-file">choose file</button></p>`
              }
            </div>
            <span class="field-divider">or paste a paper link</span>
            <input id="source" value="${escapeHtml(state.sourceInput)}" placeholder="https://arxiv.org/abs/..." />
            <div class="artifact-footer artifact-footer-simple">
              <button class="primary" id="start-review">Start Review</button>
            </div>
          </div>
        </section>
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
          <div class="pulse" aria-hidden="true"></div>
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
        <p>The task is complete. This review artifact is ready to read, inspect, and use.</p>
      </div>
      ${state.reviewId ? `<div class="action-row result-actions"><button class="primary primary-compact" id="download-artifact">Download review</button></div>` : ""}
      <article class="report">
        ${state.resultText ? markdownToHtml(state.resultText) : "<p>No final artifact received yet.</p>"}
      </article>
    </div>
  `;
}

async function uploadFile(file: File): Promise<void> {
  const form = new FormData();
  form.append("file", file);
  const resp = await authFetch("/upload", { method: "POST", body: form });
  if (!resp.ok) {
    const msg = await readErrorMessage(resp, "Upload failed");
    render();
    return;
  }
  const data = (await resp.json()) as { path: string; filename: string };
  state.uploadedSource = data.path;
  state.uploadedFilename = data.filename;

  render();
}

function bindEvents(): void {
  document.querySelector<HTMLFormElement>("#auth-form")?.addEventListener("submit", submitAccessKey);

  const source = document.querySelector<HTMLInputElement>("#source");
  source?.addEventListener("change", () => {
    state.sourceInput = source.value.trim();
  });

  const dropZone = document.querySelector<HTMLDivElement>("#drop-zone");
  const fileInput = document.querySelector<HTMLInputElement>("#file-input");
  document.querySelector<HTMLButtonElement>("#pick-file")?.addEventListener("click", () => fileInput?.click());
  fileInput?.addEventListener("change", () => {
    const file = fileInput.files?.[0];
    if (file) uploadFile(file);
  });
  dropZone?.addEventListener("dragover", (e) => { e.preventDefault(); dropZone.classList.add("drag-active"); });
  dropZone?.addEventListener("dragleave", () => dropZone.classList.remove("drag-active"));
  dropZone?.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("drag-active");
    const file = e.dataTransfer?.files[0];
    if (file) uploadFile(file);
  });

  const mode = document.querySelector<HTMLSelectElement>("#mode");
  mode?.addEventListener("change", () => {
    state.mode = mode.value as ReviewMode;
    render();
  });

  document.querySelector<HTMLButtonElement>("#start-review")?.addEventListener("click", startReview);
  document.querySelector<HTMLButtonElement>("#download-artifact")?.addEventListener("click", downloadArtifact);
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
  const source = state.uploadedSource ?? state.sourceInput.trim();

  render();

  try {
    const response = await authFetch("/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source,
        filename: state.uploadedFilename,
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

    openStream(data.review_id);
    render();
  } catch (error) {
    state.stage = "ready";
    state.statusText = "Could not reach backend.";

    render();
  }
}

function openStream(reviewId: string): void {
  closeStream();
  const token = encodeURIComponent(state.accessKey ?? "");
  stream = new EventSource(`/review/${reviewId}/stream?token=${token}`);

  stream.onmessage = (event) => {
    handleEvent(JSON.parse(event.data) as StreamEvent);
  };

  stream.onerror = () => {
    if (stream?.readyState === EventSource.CLOSED && !state.resultText && state.stage !== "ready") {
      clearAccessKey();
      render();
      return;
    }

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

  }

  if (event.type === "result") {
    state.resultText = event.text ?? "";
    state.stage = "complete";
    state.statusText = "Review complete.";

  }

  if (event.type === "error") {
    state.stage = "ready";
    state.statusText = "Run failed.";

  }

  render();
}

async function submitAnswers(event: SubmitEvent): Promise<void> {
  event.preventDefault();
  if (!state.reviewId) {

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

  render();

  try {
    const response = await authFetch(`/review/${state.reviewId}/answer`, {
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

    render();
  }
}

async function downloadArtifact(): Promise<void> {
  if (!state.reviewId) return;
  const resp = await authFetch(`/review/${state.reviewId}/artifact`);
  if (!resp.ok) return;
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${state.reviewId}.md`;
  a.click();
  URL.revokeObjectURL(url);
}

function closeStream(): void {
  stream?.close();
  stream = null;
}

async function submitAccessKey(event: SubmitEvent): Promise<void> {
  event.preventDefault();
  const form = event.currentTarget as HTMLFormElement;
  const formData = new FormData(form);
  const accessKey = formData.get("access-key")?.toString().trim() ?? "";
  if (!accessKey) {
    return;
  }
  state.accessKey = accessKey;
  sessionStorage.setItem(ACCESS_KEY_STORAGE, accessKey);
  render();
}

async function authFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  if (state.accessKey) {
    headers.set("Authorization", `Bearer ${state.accessKey}`);
  }

  const response = await fetch(input, { ...init, headers });
  if (response.status === 401) {
    clearAccessKey();
  }
  return response;
}

function clearAccessKey(): void {
  closeStream();
  sessionStorage.removeItem(ACCESS_KEY_STORAGE);
  state.accessKey = null;
  state.stage = "ready";
  state.reviewId = null;
  state.sessionId = null;
  state.resultText = "";
  state.progress = [];
  state.questions = [];
}

async function bootstrap(): Promise<void> {
  try {
    const response = await fetch("/auth/config");
    if (response.ok) {
      const data = (await response.json()) as { auth_required?: boolean };
      state.authRequired = Boolean(data.auth_required);
    } else {
      state.authRequired = true;
    }
  } catch {
    state.authRequired = true;
  } finally {
    state.authChecked = true;
    render();
  }
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

void bootstrap();
