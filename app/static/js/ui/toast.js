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

// Messages that vanish on a timer are hard to read for some people, so the timer stops while
// the pointer is over the message or keyboard focus is inside it.
function autoDismiss(element, duration) {
  let remaining = duration;
  let startedAt = 0;
  let timer = null;

  const start = () => {
    if (timer !== null) return;
    startedAt = Date.now();
    timer = setTimeout(() => element.remove(), remaining);
  };
  const pause = () => {
    if (timer === null) return;
    clearTimeout(timer);
    timer = null;
    remaining -= Date.now() - startedAt;
  };

  element.addEventListener("mouseenter", pause);
  element.addEventListener("mouseleave", start);
  element.addEventListener("focusin", pause);
  element.addEventListener("focusout", start);
  start();
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
  autoDismiss(element, kind === "error" ? 9000 : 5000);
}
