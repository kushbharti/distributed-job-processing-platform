import { api, userMessage } from "../api.js";
import { h } from "../ui/dom.js";
import { emptyState } from "../ui/empty.js";
import { formatDuration, timeEl } from "../ui/format.js";
import { lastPageOffset, pagination, readOffset } from "../ui/pagination.js";
import { createPoller } from "../ui/poll.js";
import { ACTIVE_STATUSES, statusBadge } from "../ui/status.js";
import { toast } from "../ui/toast.js";

const LIMIT = 20;

// The filter chips. "In progress" covers four server-side statuses at once.
const GROUPS = [
  { key: "all", label: "All", statuses: [] },
  { key: "active", label: "In progress", statuses: ACTIVE_STATUSES },
  { key: "completed", label: "Completed", statuses: ["COMPLETED"] },
  { key: "failed", label: "Failed", statuses: ["FAILED"] },
  { key: "cancelled", label: "Cancelled", statuses: ["CANCELLED"] },
];

function sumStatuses(stats, statuses) {
  return statuses.reduce(
    (sum, status) => sum + (stats.by_status[status] ?? 0),
    0,
  );
}

function details(job) {
  switch (job.status) {
    case "PROCESSING":
      return h(
        "div",
        { class: "details" },
        h("progress", {
          class: "bar",
          max: "100",
          value: String(job.progress),
          "aria-label": `Progress for ${job.document_filename}`,
        }),
        h(
          "span",
          { class: "details__text" },
          `${job.current_stage ?? "Working"}, ${job.progress}%`,
        ),
      );
    case "FAILED":
    case "RETRYING":
      return h(
        "span",
        {
          class: "details__text details__text--clip",
          title: job.error_message ?? "",
        },
        job.error_message ?? job.current_stage ?? "",
      );
    case "COMPLETED": {
      const took = formatDuration(job.started_at, job.completed_at);
      return h(
        "span",
        { class: "details__text" },
        took ? `Took ${took}` : "Done",
      );
    }
    default:
      return h("span", { class: "details__text" }, job.current_stage ?? "");
  }
}

function jobRow(job) {
  const name = job.document_filename ?? "Unnamed document";
  return h(
    "tr",
    {},
    h(
      "td",
      { class: "table__name" },
      h("a", { href: `#/jobs/${job.id}`, title: name }, name),
    ),
    h("td", {}, statusBadge(job.status)),
    h("td", {}, details(job)),
    h("td", {}, timeEl(job.created_at)),
  );
}

export default async function jobsPage({ query }) {
  let groupKey = GROUPS.some((group) => group.key === query.get("show"))
    ? query.get("show")
    : "all";
  let offset = readOffset(query);
  let stats = null;
  let data = { items: [], total: 0 };
  let loadId = 0;
  let lastSignature = "";
  let mounted = true;

  const currentGroup = () => GROUPS.find((group) => group.key === groupKey);
  const showLoadError = (error) => toast(userMessage(error), { kind: "error" });

  function syncUrl() {
    if (!mounted) return;
    const params = new URLSearchParams();
    if (groupKey !== "all") params.set("show", groupKey);
    if (offset) params.set("offset", String(offset));
    const search = params.toString();
    history.replaceState(null, "", search ? `#/jobs?${search}` : "#/jobs");
  }

  // The chips are created once and updated in place, so a refresh never steals keyboard focus.
  const chipRefs = GROUPS.map((group) => {
    const count = h("span", { class: "chip__count" }, "0");
    const button = h(
      "button",
      {
        type: "button",
        class: "chip",
        "aria-pressed": "false",
        onclick: () => choose(group.key),
      },
      group.label,
      count,
    );
    return { group, button, count };
  });
  const chips = h(
    "div",
    { class: "chips", role: "group", "aria-label": "Show jobs" },
    chipRefs.map((ref) => ref.button),
  );
  const listRegion = h("div", {});

  function updateChips() {
    for (const { group, button, count } of chipRefs) {
      button.setAttribute("aria-pressed", String(group.key === groupKey));
      count.textContent = String(
        group.key === "all" ? stats.total : sumStatuses(stats, group.statuses),
      );
    }
  }

  function listParams() {
    const params = new URLSearchParams({
      limit: String(LIMIT),
      offset: String(offset),
    });
    for (const status of currentGroup().statuses)
      params.append("status", status);
    return params;
  }

  async function load({ silent = false } = {}) {
    const id = ++loadId;
    if (!silent) listRegion.setAttribute("aria-busy", "true");
    try {
      const [newStats, newData] = await Promise.all([
        api("/jobs/stats"),
        api(`/jobs?${listParams()}`),
      ]);
      if (id !== loadId) return;

      if (newData.items.length === 0 && newData.total > 0 && offset > 0) {
        offset = lastPageOffset(newData.total, LIMIT);
        syncUrl();
        return load({ silent });
      }

      const signature = JSON.stringify([newStats, newData]);
      if (silent && signature === lastSignature) return;
      lastSignature = signature;
      stats = newStats;
      data = newData;
      render();
    } finally {
      if (id === loadId) listRegion.removeAttribute("aria-busy");
    }
  }

  const poller = createPoller({
    task: () => load({ silent: true }),
    shouldContinue: () =>
      mounted && stats !== null && sumStatuses(stats, ACTIVE_STATUSES) > 0,
  });

  function choose(key) {
    if (key === groupKey) return;
    groupKey = key;
    offset = 0;
    syncUrl();
    load().catch(showLoadError);
  }

  function goToOffset(next) {
    offset = next;
    syncUrl();
    load().catch(showLoadError);
  }

  function render() {
    updateChips();

    if (data.items.length === 0) {
      const nothingAtAll = groupKey === "all" && stats.total === 0;
      listRegion.replaceChildren(
        nothingAtAll
          ? emptyState({
              title: "No jobs yet",
              text: "Process a document and its progress will show up here.",
              action: h(
                "a",
                { class: "btn btn--primary", href: "#/documents" },
                "Go to documents",
              ),
            })
          : emptyState({
              title: "No jobs match this filter",
              action: h(
                "button",
                {
                  type: "button",
                  class: "btn btn--secondary",
                  onclick: () => choose("all"),
                },
                "Show all jobs",
              ),
            }),
      );
      poller.schedule();
      return;
    }

    const table = h(
      "div",
      {
        class: "table-wrap",
        tabindex: "0",
        role: "region",
        "aria-label": "Jobs",
      },
      h(
        "table",
        { class: "table" },
        h(
          "thead",
          {},
          h(
            "tr",
            {},
            h("th", { scope: "col" }, "File"),
            h("th", { scope: "col" }, "Status"),
            h("th", { scope: "col" }, "Details"),
            h("th", { scope: "col" }, "Created"),
          ),
        ),
        h("tbody", {}, data.items.map(jobRow)),
      ),
    );
    const pager = pagination({
      total: data.total,
      limit: LIMIT,
      offset,
      onChange: goToOffset,
    });
    listRegion.replaceChildren(...[table, pager].filter(Boolean));
    poller.schedule();
  }

  await load(); // a failure here reaches the router, which shows the error page

  return {
    title: "Jobs",
    node: h(
      "div",
      {},
      h(
        "div",
        { class: "page__head" },
        h("h1", {}, "Jobs"),
        h(
          "p",
          { class: "page__sub" },
          "Everything you've sent for processing. Open a job to see its result.",
        ),
      ),
      chips,
      listRegion,
    ),
    cleanup() {
      mounted = false;
      poller.stop();
    },
  };
}
