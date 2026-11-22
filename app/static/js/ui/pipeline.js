import { h } from "./dom.js";

// The seven stages the worker reports (see app/services/processing_service.py).
// `stage` is the worker's text; `at` is the progress value it reports when that stage starts.
export const STAGES = [
  {
    stage: "Validating document",
    at: 5,
    label: "Check that the file is a readable PDF",
  },
  {
    stage: "Reading metadata",
    at: 15,
    label: "Read the title, author and dates",
  },
  {
    stage: "Extracting text",
    at: 40,
    label: "Pull out the text, page by page",
  },
  { stage: "Cleaning text", at: 55, label: "Fix line breaks and split words" },
  {
    stage: "Generating summary",
    at: 75,
    label: "Pick the sentences that carry the summary",
  },
  { stage: "Generating report", at: 90, label: "Build the report as a PDF" },
  { stage: "Saving results", at: 95, label: "Save everything" },
];

export function pipeline({ intro = false, label = "Processing steps" } = {}) {
  const steps = STAGES.map((step, index) => {
    // The empty span holds a state word for screen readers ("(done)", "(failed)")
    const item = h(
      "li",
      { class: "pipeline__step", "data-stage": step.stage },
      step.label,
      h("span", { class: "visually-hidden" }),
    );
    item.style.setProperty("--i", String(index)); // CSSOM, so it also works under a strict CSP
    return item;
  });
  return h(
    "ol",
    {
      class: intro ? "pipeline pipeline--intro" : "pipeline",
      role: "list",
      "aria-label": label,
    },
    steps,
  );
}

// Index of the stage that was running at this progress value (-1 if none yet).
export function stageIndex(progress) {
  let index = -1;
  STAGES.forEach((step, i) => {
    if (progress >= step.at) index = i;
  });
  return index;
}

const NOT_STARTED = new Set(["PENDING", "QUEUED", "RETRYING"]);
const STATE_TEXT = {
  "is-done": " (done)",
  "is-active": " (in progress)",
  "is-failed": " (failed)",
};

// Colours the track for a job. Steps before the current one are done; the current one is
// active while processing, failed if the job failed, and plain if it was cancelled.
export function updatePipeline(list, { status, progress }) {
  const index = NOT_STARTED.has(status) ? -1 : stageIndex(progress);

  Array.from(list.children).forEach((item, i) => {
    let state = "";
    if (status === "COMPLETED") state = "is-done";
    else if (i < index) state = "is-done";
    else if (i === index && status === "PROCESSING") state = "is-active";
    else if (i === index && status === "FAILED") state = "is-failed";

    item.classList.remove("is-done", "is-active", "is-failed");
    if (state) item.classList.add(state);
    if (state === "is-active") item.setAttribute("aria-current", "step");
    else item.removeAttribute("aria-current");
    item.lastElementChild.textContent = STATE_TEXT[state] ?? "";
  });
}
