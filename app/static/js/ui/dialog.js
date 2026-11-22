import { h } from "./dom.js";

// Asks for confirmation. Resolves to true only if the person chose the confirm button.
// Cancel is focused first, so pressing Enter by reflex never destroys anything.
export function confirmDialog({ title, message, confirmLabel = "Confirm", danger = false }) {
  return new Promise((resolve) => {
    const dialog = h(
      "dialog",
      { class: "dialog", "aria-labelledby": "dialog-title" },
      h(
        "form",
        { method: "dialog", class: "dialog__body" },
        h("h2", { id: "dialog-title" }, title),
        h("p", {}, message),
        h(
          "div",
          { class: "dialog__actions" },
          h("button", { type: "submit", value: "cancel", class: "btn btn--secondary", autofocus: true }, "Cancel"),
          h(
            "button",
            { type: "submit", value: "confirm", class: `btn ${danger ? "btn--danger-solid" : "btn--primary"}` },
            confirmLabel,
          ),
        ),
      ),
    );

    dialog.addEventListener("close", () => {
      resolve(dialog.returnValue === "confirm"); // Escape leaves returnValue empty, which means "no"
      dialog.remove();
    });

    document.body.append(dialog);
    dialog.showModal();
  });
}