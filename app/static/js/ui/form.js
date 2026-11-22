import { h } from "./dom.js";

export const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// A labelled input with a message line underneath for hints and errors.
export function field({
  id,
  label,
  type = "text",
  autocomplete,
  hint = "",
  attrs = {},
}) {
  const message = h("p", { id: `${id}-msg`, class: "field__msg" }, hint);
  const input = h("input", {
    id,
    name: id,
    type,
    autocomplete,
    "aria-describedby": `${id}-msg`,
    "aria-required": "true",
    ...attrs,
  });
  const root = h(
    "div",
    { class: "field" },
    h("label", { for: id }, label),
    input,
    message,
  );

  return {
    root,
    input,
    setError(text) {
      root.classList.toggle("field--error", Boolean(text));
      input.setAttribute("aria-invalid", text ? "true" : "false");
      message.textContent = text || hint;
    },
  };
}

// A form-level error area. It exists from the start so screen readers announce what appears in it.
export function errorSlot() {
  const node = h("div", { role: "alert" });
  return {
    node,
    show(text) {
      node.replaceChildren(h("p", { class: "notice notice--error" }, text));
    },
    clear() {
      node.replaceChildren();
    },
  };
}

// Runs `run` on submit, disables the button while it works, and ignores repeat clicks.
export function bindSubmit(form, button, busyLabel, run) {
  const idleLabel = button.textContent;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (button.disabled) return;
    button.disabled = true;
    button.textContent = busyLabel;
    try {
      await run();
    } finally {
      button.disabled = false;
      button.textContent = idleLabel;
    }
  });
}
