import { h } from "./dom.js";

// The seven stages the worker reports (see app/services/processing_service.py), with a
// plain-language description of each. `stage` must match the worker's text exactly,
// because Stage F4 uses it to place live progress on the track.
export const STAGES = [
  { stage: "Validating document", label: "Check that the file is a readable PDF" },
  { stage: "Reading metadata", label: "Read the title, author and dates" },
  { stage: "Extracting text", label: "Pull out the text, page by page" },
  { stage: "Cleaning text", label: "Fix line breaks and split words" },
  { stage: "Generating summary", label: "Pick the sentences that carry the summary" },
  { stage: "Generating report", label: "Build the report as a PDF" },
  { stage: "Saving results", label: "Save everything" },
];

export function pipeline({ intro = false, label = "Processing steps" } = {}) {
  const steps = STAGES.map((step, index) => {
    const item = h("li", { class: "pipeline__step", "data-stage": step.stage }, step.label);
    item.style.setProperty("--i", String(index)); // CSSOM, so it also works under a strict CSP
    return item;
  });
  return h(
    "ol",
    { class: intro ? "pipeline pipeline--intro" : "pipeline", role: "list", "aria-label": label },
    steps,
  );
}