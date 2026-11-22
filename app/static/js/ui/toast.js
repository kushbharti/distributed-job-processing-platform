import { h } from "./dom.js";

const MAX_VISIBLE = 4;
let region = null;

function getRegion() {
  if (!region) {
    region = h("div", {
      class: "toasts",
      role: "status",
      "aria-live": "polite",
    });
    document.body.append(region);
  }
  return region;
}

// A short message in the corner. Errors use role="alert" so screen readers announce them at once.
export function toast(message, { kind = "info", action } = {}) {
  const element = h(
    "div",
    { class: `toast toast--${kind}`, role: kind === "error" ? "alert" : null },
    h("p", { class: "toast__text" }, message),
    action &&
      h("a", { class: "toast__action", href: action.href }, action.label),
    h(
      "button",
      {
        type: "button",
        class: "toast__close",
        "aria-label": "Dismiss",
        onclick: () => element.remove(),
      },
      "×",
    ),
  );

  const container = getRegion();
  container.append(element);
  while (container.children.length > MAX_VISIBLE)
    container.firstElementChild.remove();
  setTimeout(() => element.remove(), kind === "error" ? 9000 : 5000);
}
