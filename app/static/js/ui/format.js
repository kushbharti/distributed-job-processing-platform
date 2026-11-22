import { h } from "./dom.js";

const dateFormat = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});

export function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value >= 10 ? Math.round(value) : value.toFixed(1)} ${units[unit]}`;
}

export function formatDate(iso) {
  return iso ? dateFormat.format(new Date(iso)) : "";
}

// A <time> element: readable for people, machine-readable for everything else.
export function timeEl(iso) {
  return iso ? h("time", { datetime: iso }, formatDate(iso)) : "";
}

export function formatDuration(startIso, endIso) {
  if (!startIso || !endIso) return "";
  const seconds = Math.max(
    0,
    Math.round((new Date(endIso) - new Date(startIso)) / 1000),
  );
  if (seconds < 60) return `${seconds} s`;
  return `${Math.floor(seconds / 60)} min ${seconds % 60} s`;
}
