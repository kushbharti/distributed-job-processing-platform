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

// PDF dates look like D:20261117173430+05'00'
export function formatPdfDate(value) {
  const match =
    /^D:(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?(?:([Zz+-])(\d{2})?'?(\d{2})?'?)?/.exec(
      value,
    );
  if (!match) return value;
  const [
    ,
    year,
    month = "01",
    day = "01",
    hour = "00",
    minute = "00",
    second = "00",
    sign,
    offsetHour = "00",
    offsetMinute = "00",
  ] = match;
  let iso = `${year}-${month}-${day}T${hour}:${minute}:${second}`;
  if (sign === "Z" || sign === "z") iso += "Z";
  else if (sign) iso += `${sign}${offsetHour}:${offsetMinute}`;
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? value : dateFormat.format(date);
}
