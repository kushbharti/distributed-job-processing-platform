import { h } from "./dom.js";

// One line in the upload list: file name, status text, progress bar and a cancel/dismiss button.
export function uploadRow(name, { onCancel }) {
  const status = h("span", { class: "upload__status" }, "Waiting");
  const bar = h("progress", {
    class: "bar",
    max: "100",
    value: "0",
    "aria-label": `Upload progress for ${name}`,
  });
  const action = h(
    "button",
    { type: "button", class: "btn btn--quiet btn--small", onclick: onCancel },
    "Cancel",
  );
  const node = h(
    "li",
    { class: "upload" },
    h(
      "div",
      { class: "upload__info" },
      h("span", { class: "upload__name", title: name }, name),
      status,
    ),
    bar,
    action,
  );

  return {
    node,
    setProgress(fraction) {
      const percent = Math.round(fraction * 100);
      bar.value = percent;
      // At 100% the bytes are sent, but the server is still checking the PDF
      status.textContent =
        percent >= 100 ? "Checking the file…" : `Uploading, ${percent}%`;
    },
    setDone() {
      bar.value = 100;
      status.textContent = "Uploaded";
      node.classList.add("is-done");
      action.hidden = true;
    },
    setError(text) {
      bar.hidden = true;
      status.setAttribute("role", "alert"); // announce the problem
      status.textContent = text;
      node.classList.add("is-error");
      action.textContent = "Dismiss";
      action.hidden = false;
    },
  };
}
