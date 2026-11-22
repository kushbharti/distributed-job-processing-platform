import { ApiError, api } from "../api.js";
import { currentUser } from "../auth.js";
import { h } from "../ui/dom.js";

const LABELS = { database: "Database", redis: "Redis" };

// /ready answers 503 with the per-service results in the body when something is down.
async function readiness() {
  try {
    return (await api("/ready", { auth: false })).checks;
  } catch (error) {
    if (error instanceof ApiError && error.data?.detail?.checks)
      return error.data.detail.checks;
    return null;
  }
}

// Temporary: Stage F2 replaces this with the real documents page.
export default async function documentsPage() {
  const [user, checks] = await Promise.all([currentUser(), readiness()]);

  const rows = checks
    ? Object.entries(checks).map(([name, state]) =>
        h(
          "div",
          { class: "facts__row" },
          h("dt", {}, LABELS[name] ?? name),
          h(
            "dd",
            { class: state === "ok" ? "" : "facts__bad" },
            state === "ok" ? "Running" : "Unavailable",
          ),
        ),
      )
    : [];

  return {
    title: "Documents",
    node: h(
      "div",
      {},
      h(
        "div",
        { class: "page__head" },
        h("h1", {}, "Documents"),
        h(
          "p",
          { class: "page__sub" },
          "Uploading arrives in the next stage. For now this page confirms you're signed in and that the services behind the API are running.",
        ),
      ),
      h(
        "section",
        { class: "panel" },
        h(
          "dl",
          { class: "facts" },
          h(
            "div",
            { class: "facts__row" },
            h("dt", {}, "Signed in as"),
            h("dd", {}, user.email),
          ),
          rows,
        ),
      ),
      checks === null &&
        h(
          "p",
          { class: "notice notice--error" },
          "The API's status check couldn't be reached.",
        ),
    ),
  };
}
