import { ApiError, api, download, userMessage } from "../api.js";
import { watchJob } from "../live.js";
import { navigate } from "../router.js";
import { confirmDialog } from "../ui/dialog.js";
import { h } from "../ui/dom.js";
import { formatDuration, formatPdfDate, timeEl } from "../ui/format.js";
import { pipeline, updatePipeline } from "../ui/pipeline.js";
import { createPoller } from "../ui/poll.js";
import { ACTIVE, statusBadge, statusLabel } from "../ui/status.js";
import { toast } from "../ui/toast.js";

const META_LABELS = {
  title: "Title",
  author: "Author",
  subject: "Subject",
  keywords: "Keywords",
  creator: "Created with",
  producer: "Produced by",
  creationDate: "Created",
  modDate: "Modified",
};
const DATE_KEYS = new Set(["creationDate", "modDate"]);

function factsList(rows) {
  return h(
    "dl",
    { class: "facts" },
    rows
      .filter(([, value]) => value)
      .map(([label, value]) =>
        h(
          "div",
          { class: "facts__row" },
          h("dt", {}, label),
          h("dd", {}, value),
        ),
      ),
  );
}

function section(title, ...children) {
  return h(
    "section",
    { class: "job-section" },
    h("h2", {}, title),
    ...children,
  );
}

function fileStem(name) {
  return (
    name.replace(/\.pdf$/i, "").replace(/[\\/:*?"<>|]+/g, "-") || "document"
  );
}

export default async function jobPage({ params }) {
  let job = await api(`/jobs/${encodeURIComponent(params.id)}`);
  let result = null;
  let resultError = "";
  let connection = "connecting";
  let live = false;
  let watcher = null;
  let mounted = true;
  let refreshId = 0;
  let shownStatus = null;
  let shownAction = "";
  let shownResult = "";

  const isActive = () => ACTIVE.has(job.status);
  const fileName = () => job.document_filename ?? "Document";

  // ---- Fixed parts of the page ----

  const metaEl = h("p", { class: "job-meta" });
  const actionsEl = h("div", { class: "job-actions" });
  const trackEl = pipeline({ label: "Processing steps" });
  const connectionEl = h("p", { class: "connection" });
  const messageEl = h("div", {});
  const factsEl = h("div", {});
  const resultEl = h("div", { class: "job-results" });
  const announcer = h("p", { class: "visually-hidden", role: "status" });

  // ---- Loading ----

  async function loadResult() {
    resultError = "";
    try {
      result = await api(`/jobs/${job.id}/result`);
    } catch (error) {
      result = null;
      resultError = userMessage(error);
    }
  }

  async function applyJob(next) {
    job = next;
    if (job.status !== "COMPLETED") {
      result = null;
      resultError = "";
    } else if (!result) {
      await loadResult();
    }
    if (mounted) paint();
  }

  async function refresh() {
    const id = ++refreshId;
    let next;
    try {
      next = await api(`/jobs/${job.id}`);
    } catch (error) {
      if (error instanceof ApiError && error.status === 404 && mounted) {
        toast("This job no longer exists.", { kind: "error" });
        navigate("/jobs");
      }
      throw error;
    }
    if (id !== refreshId || !mounted) return; // a newer refresh has taken over
    await applyJob(next);
  }

  // When the socket is not connected, ask the API every few seconds instead.
  const poller = createPoller({
    task: refresh,
    shouldContinue: () => mounted && isActive() && !live,
    intervalMs: 3000,
  });

  // ---- Live updates ----

  function syncWatching() {
    if (!mounted) return;
    if (isActive() && !watcher) {
      watcher = watchJob(job.id, {
        onMessage: onLiveMessage,
        onStatus: onLiveStatus,
      });
    } else if (!isActive() && watcher) {
      watcher.close();
      watcher = null;
      live = false;
      connection = "idle";
    }
  }

  function onLiveMessage({ type, data }) {
    const previous = job.status;
    job = { ...job, status: data.status, error_message: data.error_message };
    if (type === "snapshot") {
      job.progress = data.progress;
      job.current_stage = data.current_stage;
    } else {
      job.current_stage = data.current_stage ?? job.current_stage;
      // Failed and retrying events carry progress 0; only trust it while processing.
      if (data.status === "PROCESSING") job.progress = data.progress;
    }
    paint();

    if (data.status !== previous) {
      // Fetch the full record: timestamps, retry count, and (when finished) the result.
      refresh().catch(() => {
        if (job.status === "COMPLETED" && !result) {
          resultError = "Couldn't load the results.";
          paint();
        }
      });
    }
  }

  function onLiveStatus(state) {
    connection = state;
    live = state === "live";
    paintConnection();
    if (!live) poller.schedule();
    // An invalid token ends the session inside the API client; a missing job navigates away.
    if (state === "unauthorized" || state === "missing")
      refresh().catch(() => {});
    if (state === "closed" && isActive()) refresh().catch(() => {});
  }

  // ---- Actions ----

  const focusAction = () => actionsEl.querySelector("button")?.focus();

  async function onCancel(event) {
    const button = event.currentTarget;
    const confirmed = await confirmDialog({
      title: "Cancel this job?",
      message:
        "Processing stops and anything produced so far is discarded. You can retry the job afterwards.",
      confirmLabel: "Cancel job",
      cancelLabel: "Keep running",
      danger: true,
    });
    if (!confirmed || !mounted) return;

    button.disabled = true;
    try {
      await applyJob(await api(`/jobs/${job.id}/cancel`, { method: "POST" }));
    } catch (error) {
      toast(userMessage(error), { kind: "error" });
      button.disabled = false;
      if (error instanceof ApiError && error.status === 409)
        refresh().catch(() => {}); // it finished first
      return;
    }
    focusAction();
  }

  async function onRetry(event) {
    const button = event.currentTarget;
    button.disabled = true;
    try {
      await applyJob(await api(`/jobs/${job.id}/retry`, { method: "POST" }));
    } catch (error) {
      toast(userMessage(error), { kind: "error" });
      button.disabled = false;
      return;
    }
    focusAction();
  }

  async function onProcessAgain(event) {
    const button = event.currentTarget;
    button.disabled = true;
    try {
      const next = await api("/jobs", {
        method: "POST",
        json: { document_id: job.document_id },
      });
      navigate(`/jobs/${next.id}`);
    } catch (error) {
      toast(userMessage(error), { kind: "error" });
      button.disabled = false;
    }
  }

  function downloadButton(label, path, filename) {
    const button = h(
      "button",
      {
        type: "button",
        class: "btn btn--secondary",
        onclick: async () => {
          button.disabled = true;
          button.textContent = "Preparing…";
          try {
            await download(path, filename);
          } catch (error) {
            toast(userMessage(error), { kind: "error" });
          } finally {
            button.disabled = false;
            button.textContent = label;
          }
        },
      },
      label,
    );
    return button;
  }

  // ---- Drawing ----

  function statusMessage() {
    switch (job.status) {
      case "PENDING":
        return h(
          "p",
          { class: "stage-line" },
          "Waiting to be sent to the queue.",
        );
      case "QUEUED":
        return h(
          "p",
          { class: "stage-line" },
          "In the queue. A worker will pick it up shortly.",
        );
      case "PROCESSING":
        return h(
          "p",
          { class: "stage-line" },
          `${job.current_stage ?? "Working"}, ${job.progress}%`,
        );
      case "RETRYING":
        return h(
          "p",
          { class: "notice notice--info" },
          job.error_message ?? "Trying again shortly.",
        );
      case "FAILED":
        return h(
          "p",
          { class: "notice notice--error" },
          job.error_message ?? "The job failed.",
        );
      case "CANCELLED":
        return h(
          "p",
          { class: "stage-line" },
          "This job was cancelled before it finished.",
        );
      case "COMPLETED": {
        const took = formatDuration(job.started_at, job.completed_at);
        return h(
          "p",
          { class: "stage-line" },
          took ? `Finished in ${took}.` : "Finished.",
        );
      }
      default:
        return null;
    }
  }

  function paintConnection() {
    let text = "";
    if (isActive()) {
      text =
        { live: "Live updates on", connecting: "Connecting for live updates…" }[
          connection
        ] ?? "Live updates paused. Checking every few seconds.";
    }
    connectionEl.textContent = text;
    connectionEl.classList.toggle(
      "is-live",
      isActive() && connection === "live",
    );
  }

  function actionKind() {
    if (isActive()) return "cancel";
    return job.status === "COMPLETED" ? "again" : "retry";
  }

  // Rebuilt only when the kind of button changes, so keyboard focus survives routine updates.
  function renderActions() {
    const kind = actionKind();
    if (kind === shownAction) return;
    shownAction = kind;
    const button = {
      cancel: () =>
        h(
          "button",
          { type: "button", class: "btn btn--danger", onclick: onCancel },
          "Cancel job",
        ),
      again: () =>
        h(
          "button",
          {
            type: "button",
            class: "btn btn--secondary",
            onclick: onProcessAgain,
          },
          "Process again",
        ),
      retry: () =>
        h(
          "button",
          { type: "button", class: "btn btn--primary", onclick: onRetry },
          "Retry job",
        ),
    }[kind]();
    actionsEl.replaceChildren(button);
  }

  function resultKey() {
    if (job.status !== "COMPLETED") return "none";
    if (result) return "ready";
    return resultError ? "error" : "loading";
  }

  function resultSections() {
    const stats = result.stats ?? {};
    const properties = Object.entries(result.metadata ?? {})
      .filter(
        ([key, value]) => META_LABELS[key] && value && !/^\(.*\)$/.test(value),
      ) // hide "(unspecified)" placeholders
      .map(([key, value]) => [
        META_LABELS[key],
        DATE_KEYS.has(key) ? formatPdfDate(value) : value,
      ]);
    const stem = fileStem(fileName());

    return [
      section(
        "Summary",
        h(
          "p",
          { class: "summary" },
          result.summary || "No summary could be generated.",
        ),
        result.keywords.length > 0 &&
          h(
            "p",
            { class: "keywords" },
            h("span", { class: "muted" }, "Frequent words: "),
            result.keywords.join(", "),
          ),
      ),
      section(
        "Document statistics",
        factsList([
          ["Pages", stats.pages != null ? stats.pages.toLocaleString() : null],
          ["Words", stats.words != null ? stats.words.toLocaleString() : null],
          [
            "Characters",
            stats.characters != null ? stats.characters.toLocaleString() : null,
          ],
          [
            "Reading time",
            stats.reading_minutes ? `About ${stats.reading_minutes} min` : null,
          ],
        ]),
      ),
      properties.length > 0 &&
        section("Document properties", factsList(properties)),
      section(
        "Downloads",
        h(
          "div",
          { class: "job-downloads" },
          downloadButton(
            "Download report (PDF)",
            `/jobs/${job.id}/result/report`,
            `${stem}-report.pdf`,
          ),
          downloadButton(
            "Download extracted text",
            `/jobs/${job.id}/result/text`,
            `${stem}-text.txt`,
          ),
        ),
        h(
          "p",
          { class: "job-note" },
          "The report holds the summary, statistics and properties. The text file has everything that was extracted.",
        ),
      ),
    ];
  }

  function renderResult() {
    const key = resultKey();
    if (key === shownResult) return;
    shownResult = key;

    if (key === "none") {
      resultEl.replaceChildren();
    } else if (key === "loading") {
      resultEl.replaceChildren(h("p", { class: "muted" }, "Loading results…"));
    } else if (key === "error") {
      resultEl.replaceChildren(
        section(
          "Results",
          h("p", { class: "notice notice--error" }, resultError),
          h(
            "p",
            {},
            h(
              "button",
              {
                type: "button",
                class: "btn btn--secondary",
                onclick: async () => {
                  await loadResult();
                  paint();
                },
              },
              "Try again",
            ),
          ),
        ),
      );
    } else {
      resultEl.replaceChildren(...resultSections().filter(Boolean));
    }
  }

  function paint() {
    const statusChanged = shownStatus !== job.status;

    metaEl.replaceChildren(
      statusBadge(job.status),
      h("span", { class: "muted" }, "Created ", timeEl(job.created_at)),
    );
    renderActions();
    updatePipeline(trackEl, job);
    messageEl.replaceChildren(...[statusMessage()].filter(Boolean));
    factsEl.replaceChildren(
      factsList([
        ["Started", timeEl(job.started_at)],
        ["Finished", timeEl(job.completed_at)],
        ["Time taken", formatDuration(job.started_at, job.completed_at)],
        ["Retries", job.retry_count > 0 ? String(job.retry_count) : null],
        ["Job ID", h("code", { class: "mono" }, job.id)],
      ]),
    );
    paintConnection();
    renderResult();

    if (statusChanged && shownStatus !== null) {
      announcer.textContent = `Job ${statusLabel(job.status).toLowerCase()}.`;
    }
    shownStatus = job.status;
    syncWatching();
  }

  // ---- Start ----

  if (job.status === "COMPLETED") await loadResult();
  paint();

  return {
    title: fileName(),
    node: h(
      "div",
      {},
      h("a", { class: "back-link", href: "#/jobs" }, "Back to all jobs"),
      h(
        "div",
        { class: "job-head" },
        h("div", {}, h("h1", {}, fileName()), metaEl),
        actionsEl,
      ),
      h(
        "div",
        { class: "job-layout" },
        h(
          "section",
          { class: "job-section", "aria-labelledby": "track-title" },
          h("h2", { id: "track-title" }, "Progress"),
          trackEl,
          connectionEl,
        ),
        h("div", { class: "job-body" }, messageEl, factsEl),
      ),
      resultEl,
      announcer,
    ),
    cleanup() {
      mounted = false;
      poller.stop();
      watcher?.close();
      watcher = null;
    },
  };
}
