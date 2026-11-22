import { h } from "./dom.js";

export function readOffset(query) {
  const value = Number.parseInt(query.get("offset") ?? "0", 10);
  return Number.isFinite(value) && value > 0 ? value : 0;
}

export function lastPageOffset(total, limit) {
  return Math.max(0, (Math.ceil(total / limit) - 1) * limit);
}

export function pagination({ total, limit, offset, onChange }) {
  if (total <= limit) return null;
  const first = offset + 1;
  const last = Math.min(offset + limit, total);

  return h(
    "nav",
    { class: "pager", "aria-label": "Pagination" },
    h("p", { class: "pager__range" }, `${first}–${last} of ${total}`),
    h(
      "div",
      { class: "pager__buttons" },
      h(
        "button",
        {
          type: "button",
          class: "btn btn--secondary btn--small",
          disabled: offset === 0,
          onclick: () => onChange(Math.max(0, offset - limit)),
        },
        "Previous",
      ),
      h(
        "button",
        {
          type: "button",
          class: "btn btn--secondary btn--small",
          disabled: offset + limit >= total,
          onclick: () => onChange(offset + limit),
        },
        "Next",
      ),
    ),
  );
}
