import { h } from "./dom.js";

// An empty list is an invitation to do something, so every one names its next step.
export function emptyState({ title, text, action }) {
  return h(
    "div",
    { class: "empty" },
    h("p", { class: "empty__title" }, title),
    text && h("p", { class: "empty__text" }, text),
    action,
  );
}
