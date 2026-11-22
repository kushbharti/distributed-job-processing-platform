import { api } from "../api.js";
import { h } from "../ui/dom.js";
import { timeEl } from "../ui/format.js";
import { statusBadge } from "../ui/status.js";

// Temporary: Stage F4 replaces this with the live job page (progress track, results, downloads).
export default async function jobPage({ params }) {
  const job = await api(`/jobs/${encodeURIComponent(params.id)}`);
  const name = job.document_filename ?? "Job";
  const row = (label, value) =>
    h("div", { class: "facts__row" }, h("dt", {}, label), h("dd", {}, value));

  return {
    title: name,
    node: h(
      "div",
      {},
      h("a", { class: "back-link", href: "#/jobs" }, "Back to all jobs"),
      h(
        "div",
        { class: "page__head" },
        h("h1", {}, name),
        h(
          "p",
          { class: "page__sub" },
          "A fuller view with live progress, results and downloads arrives in the next stage.",
        ),
      ),
      h(
        "section",
        { class: "panel" },
        h(
          "dl",
          { class: "facts" },
          row("Status", statusBadge(job.status)),
          row("Stage", job.current_stage ?? "-"),
          row("Progress", `${job.progress}%`),
          row("Created", timeEl(job.created_at)),
          job.started_at && row("Started", timeEl(job.started_at)),
          job.completed_at && row("Finished", timeEl(job.completed_at)),
          job.error_message && row("Message", job.error_message),
          row("Job ID", h("code", { class: "mono" }, job.id)),
        ),
      ),
    ),
  };
}
