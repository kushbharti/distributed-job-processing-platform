import { api, upload, userMessage } from "../api.js";
import { MAX_UPLOAD_MB } from "../config.js";
import { confirmDialog } from "../ui/dialog.js";
import { h } from "../ui/dom.js";
import { emptyState } from "../ui/empty.js";
import { formatBytes, timeEl } from "../ui/format.js";
import { lastPageOffset, pagination, readOffset } from "../ui/pagination.js";
import { createPoller } from "../ui/poll.js";
import { ACTIVE, statusBadge, statusLabel } from "../ui/status.js";
import { toast } from "../ui/toast.js";
import { uploadRow } from "../ui/upload-row.js";

const LIMIT = 20;

// Uploads keep going if the person leaves this page, so warn before the tab itself is closed.
let pendingUploads = 0;
window.addEventListener("beforeunload", (event) => {
  if (pendingUploads > 0) {
    event.preventDefault();
    event.returnValue = "";
  }
});

function checkFile(file) {
  if (!file.name.toLowerCase().endsWith(".pdf"))
    return "Only PDF files can be uploaded.";
  if (file.size === 0) return "This file is empty.";
  if (file.size > MAX_UPLOAD_MB * 1024 * 1024)
    return `This file is larger than ${MAX_UPLOAD_MB} MB.`;
  return "";
}

// Some systems report no type for a PDF, and the server requires one.
function asPdf(file) {
  return file.type === "application/pdf"
    ? file
    : new File([file], file.name, { type: "application/pdf" });
}

function hasFiles(event) {
  return Array.from(event.dataTransfer?.types ?? []).includes("Files");
}

export default async function documentsPage({ query }) {
  let offset = readOffset(query);
  let data = { items: [], total: 0 };
  let loadId = 0;
  let lastSignature = "";
  let mounted = true;

  const listRegion = h("div", {});
  const countLabel = h("span", { class: "heading-count" });
  const heading = h("h2", { tabindex: "-1" }, "All documents");
  const uploadsList = h("ul", {
    class: "uploads",
    "aria-label": "Uploads",
    hidden: true,
  });
  const fileInput = h("input", {
    type: "file",
    accept: ".pdf,application/pdf",
    multiple: true,
    hidden: true,
  });

  // The address bar follows the page, so a reload or a shared link lands in the same place.
  // replaceState does not fire hashchange, so this never re-renders the page.
  function syncUrl() {
    if (!mounted) return;
    history.replaceState(
      null,
      "",
      offset ? `#/documents?offset=${offset}` : "#/documents",
    );
  }

  const showLoadError = (error) => toast(userMessage(error), { kind: "error" });

  // ---- Loading and drawing the list ----

  async function load({ silent = false } = {}) {
    const id = ++loadId;
    if (!silent) listRegion.setAttribute("aria-busy", "true");
    try {
      const result = await api(`/documents?limit=${LIMIT}&offset=${offset}`);
      if (id !== loadId) return; // a newer request has taken over

      if (result.items.length === 0 && result.total > 0 && offset > 0) {
        offset = lastPageOffset(result.total, LIMIT); // the last item on this page was deleted
        syncUrl();
        return load({ silent });
      }

      const signature = JSON.stringify(result);
      if (silent && signature === lastSignature) return; // nothing changed: leave the DOM alone
      lastSignature = signature;
      data = result;
      renderList();
    } finally {
      if (id === loadId) listRegion.removeAttribute("aria-busy");
    }
  }

  const poller = createPoller({
    task: () => load({ silent: true }),
    shouldContinue: () =>
      mounted &&
      data.items.some(
        (doc) => doc.latest_job && ACTIVE.has(doc.latest_job.status),
      ),
  });

  function renderList() {
    countLabel.textContent = data.total
      ? `${data.total} ${data.total === 1 ? "file" : "files"}`
      : "";

    if (data.items.length === 0) {
      listRegion.replaceChildren(
        emptyState({
          title: "No documents yet",
          text: "Choose a PDF above and it will appear here.",
        }),
      );
      poller.schedule();
      return;
    }

    const table = h(
      "div",
      {
        class: "table-wrap",
        tabindex: "0",
        role: "region",
        "aria-label": "Documents",
      },
      h(
        "table",
        { class: "table" },
        h(
          "thead",
          {},
          h(
            "tr",
            {},
            h("th", { scope: "col" }, "Name"),
            h("th", { scope: "col", class: "num" }, "Pages"),
            h("th", { scope: "col", class: "num" }, "Size"),
            h("th", { scope: "col" }, "Uploaded"),
            h("th", { scope: "col" }, "Latest job"),
            h(
              "th",
              { scope: "col" },
              h("span", { class: "visually-hidden" }, "Actions"),
            ),
          ),
        ),
        h("tbody", {}, data.items.map(documentRow)),
      ),
    );
    const pager = pagination({
      total: data.total,
      limit: LIMIT,
      offset,
      onChange: goToOffset,
    });
    listRegion.replaceChildren(...[table, pager].filter(Boolean));
    poller.schedule();
  }

  function documentRow(doc) {
    const job = doc.latest_job;
    const busy = Boolean(job) && ACTIVE.has(job.status);
    const processLabel = job ? "Process again" : "Process";

    return h(
      "tr",
      {},
      h("td", { class: "table__name", title: doc.filename }, doc.filename),
      h("td", { class: "num" }, doc.page_count ?? "-"),
      h("td", { class: "num" }, formatBytes(doc.file_size)),
      h("td", {}, timeEl(doc.created_at)),
      h(
        "td",
        {},
        job
          ? h(
              "a",
              {
                class: "status-link",
                href: `#/jobs/${job.id}`,
                "aria-label": `${statusLabel(job.status)} job for ${doc.filename}`,
              },
              statusBadge(job.status),
            )
          : h("span", { class: "muted" }, "Not processed"),
      ),
      h(
        "td",
        {},
        h(
          "div",
          { class: "table__actions" },
          !busy &&
            h(
              "button",
              {
                type: "button",
                class: "btn btn--secondary btn--small",
                "aria-label": `${processLabel} ${doc.filename}`,
                onclick: (event) => startJob(doc, event.currentTarget),
              },
              processLabel,
            ),
          h(
            "button",
            {
              type: "button",
              class: "btn btn--quiet btn--small",
              disabled: busy,
              title: busy ? "Cancel the running job first" : null,
              "aria-label": `Delete ${doc.filename}`,
              onclick: () => removeDocument(doc),
            },
            "Delete",
          ),
        ),
      ),
    );
  }

  function goToOffset(next) {
    offset = next;
    syncUrl();
    load().catch(showLoadError);
  }

  // ---- Actions on a document ----

  async function startJob(doc, button) {
    button.disabled = true;
    try {
      const job = await api("/jobs", {
        method: "POST",
        json: { document_id: doc.id },
      });
      toast(`Processing started for ${doc.filename}.`, {
        action: { label: "View job", href: `#/jobs/${job.id}` },
      });
    } catch (error) {
      toast(userMessage(error), { kind: "error" });
      button.disabled = false;
      return;
    }
    load({ silent: true }).catch(() => {});
  }

  async function removeDocument(doc) {
    const confirmed = await confirmDialog({
      title: `Delete ${doc.filename}?`,
      message:
        "The file and any results from processing it are removed. This can't be undone.",
      confirmLabel: "Delete",
      danger: true,
    });
    if (!confirmed) return;

    try {
      await api(`/documents/${doc.id}`, { method: "DELETE" });
    } catch (error) {
      toast(userMessage(error), { kind: "error" });
      return;
    }
    toast(`Deleted ${doc.filename}.`);
    try {
      await load({ silent: true });
    } catch (error) {
      showLoadError(error);
    }
    heading.focus(); // the button that opened the dialog no longer exists
  }

  // ---- Uploading ----

  const queue = [];
  let uploading = false;

  function removeRow(entry) {
    entry.row.node.remove();
    uploadsList.hidden = uploadsList.children.length === 0;
  }

  function settle(entry) {
    if (entry.settled) return;
    entry.settled = true;
    pendingUploads -= 1;
  }

  function cancelEntry(entry) {
    entry.controller.abort();
    const index = queue.indexOf(entry);
    if (index !== -1) queue.splice(index, 1);
    settle(entry);
    removeRow(entry);
  }

  function enqueue(file) {
    const entry = { file, controller: new AbortController(), settled: false };
    entry.row = uploadRow(file.name, { onCancel: () => cancelEntry(entry) });
    uploadsList.append(entry.row.node);
    uploadsList.hidden = false;
    pendingUploads += 1;
    queue.push(entry);
    pump();
  }

  async function uploadOne(entry) {
    const body = new FormData();
    body.append("file", asPdf(entry.file));
    entry.row.setProgress(0);

    try {
      await upload("/documents/upload", body, {
        signal: entry.controller.signal,
        onProgress: (fraction) => entry.row.setProgress(fraction),
      });
    } catch (error) {
      settle(entry);
      if (error.name === "AbortError") return; // cancelled: the row is already gone
      entry.row.setError(userMessage(error));
      return;
    }

    settle(entry);
    entry.row.setDone();
    if (mounted) {
      offset = 0; // new files appear at the top of the first page
      syncUrl();
      load({ silent: true }).catch(() => {});
      setTimeout(() => removeRow(entry), 4000);
    } else {
      toast(`Uploaded ${entry.file.name}.`);
    }
  }

  // One upload at a time keeps the progress readable and the server calm.
  async function pump() {
    if (uploading) return;
    uploading = true;
    try {
      while (queue.length > 0) await uploadOne(queue.shift());
    } finally {
      uploading = false;
    }
  }

  function addFiles(files) {
    for (const file of Array.from(files)) {
      const problem = checkFile(file);
      if (problem) {
        const row = uploadRow(file.name, {
          onCancel: () => (
            row.node.remove(),
            (uploadsList.hidden = uploadsList.children.length === 0)
          ),
        });
        uploadsList.append(row.node);
        uploadsList.hidden = false;
        row.setError(problem);
      } else {
        enqueue(file);
      }
    }
  }

  // ---- Drop zone ----

  const chooseButton = h(
    "button",
    {
      type: "button",
      class: "btn btn--primary",
      onclick: () => fileInput.click(),
    },
    "Choose files",
  );
  const dropzone = h(
    "section",
    { class: "dropzone", "aria-label": "Upload PDFs" },
    h("p", { class: "dropzone__title" }, "Drop PDF files here"),
    h(
      "p",
      { class: "dropzone__hint" },
      `PDF only, up to ${MAX_UPLOAD_MB} MB each.`,
    ),
    chooseButton,
    fileInput,
  );

  fileInput.addEventListener("change", () => {
    const files = Array.from(fileInput.files); // copy first: clearing the input empties the live list
    fileInput.value = "";
    addFiles(files);
  });

  let dragDepth = 0; // dragenter/dragleave fire for child elements too, so count them
  dropzone.addEventListener("dragenter", (event) => {
    if (!hasFiles(event)) return;
    event.preventDefault();
    dragDepth += 1;
    dropzone.classList.add("is-over");
  });
  dropzone.addEventListener("dragover", (event) => {
    if (!hasFiles(event)) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
  });
  dropzone.addEventListener("dragleave", () => {
    dragDepth = Math.max(0, dragDepth - 1);
    if (dragDepth === 0) dropzone.classList.remove("is-over");
  });
  dropzone.addEventListener("drop", (event) => {
    event.preventDefault();
    dragDepth = 0;
    dropzone.classList.remove("is-over");
    addFiles(event.dataTransfer.files);
  });

  // A file dropped beside the zone would make the browser navigate to it and leave the app.
  const ignoreStrayDrops = (event) => {
    if (hasFiles(event)) event.preventDefault();
  };
  window.addEventListener("dragover", ignoreStrayDrops);
  window.addEventListener("drop", ignoreStrayDrops);

  // ---- Start ----

  await load(); // a failure here reaches the router, which shows the error page

  return {
    title: "Documents",
    node: h(
      "div",
      {},
      h(
        "div",
        { class: "page__head" },
        h("h1", {}, "Documents"),
        h(
          "p",
          { class: "page__sub" },
          "Upload a PDF, then process it to get a summary and a report.",
        ),
      ),
      dropzone,
      uploadsList,
      h("div", { class: "section-head" }, heading, countLabel),
      listRegion,
    ),
    cleanup() {
      mounted = false;
      poller.stop();
      window.removeEventListener("dragover", ignoreStrayDrops);
      window.removeEventListener("drop", ignoreStrayDrops);
    },
  };
}
