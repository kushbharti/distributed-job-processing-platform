import { h } from "./dom.js";

export const ACTIVE_STATUSES = ["PENDING", "QUEUED", "PROCESSING", "RETRYING"];
export const ACTIVE = new Set(ACTIVE_STATUSES);

// What the worker's states are called in the interface.
const LABELS = {
  PENDING: "Waiting",
  QUEUED: "Queued",
  PROCESSING: "Processing",
  RETRYING: "Retrying",
  COMPLETED: "Completed",
  FAILED: "Failed",
  CANCELLED: "Cancelled",
};

export function statusLabel(status) {
  return LABELS[status] ?? status;
}

export function statusBadge(status) {
  return h(
    "span",
    { class: `status status--${status.toLowerCase()}` },
    statusLabel(status),
  );
}
