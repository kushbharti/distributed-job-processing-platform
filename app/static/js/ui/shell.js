import { APP_NAME } from "../config.js";
import { h } from "./dom.js";

// Add an entry here when a stage adds a page: F2 adds Documents' siblings, F3 adds Jobs.
const NAV = [{ href: "#/documents", match: "/documents", label: "Documents" }];

export function createShell({ email, onSignOut }) {
  const nav = h(
    "nav",
    { class: "nav", "aria-label": "Main" },
    NAV.map((item) =>
      h("a", { href: item.href, "data-match": item.match }, item.label),
    ),
  );

  const main = h("main", { id: "main", class: "page", tabindex: "-1" });

  const root = h(
    "div",
    { class: "shell" },
    h(
      "header",
      { class: "topbar" },
      h(
        "div",
        { class: "topbar__inner" },
        h(
          "a",
          { class: "brand", href: "#/documents" },
          h("img", {
            src: "/static/favicon.svg",
            alt: "",
            width: "24",
            height: "24",
          }),
          APP_NAME,
        ),
        nav,
        h(
          "div",
          { class: "topbar__user" },
          h("span", { class: "topbar__email", title: email }, email),
          h(
            "button",
            {
              type: "button",
              class: "btn btn--quiet btn--small",
              onclick: onSignOut,
            },
            "Sign out",
          ),
        ),
      ),
    ),
    main,
  );

  function setActive(path) {
    for (const link of nav.querySelectorAll("a")) {
      const match = link.dataset.match;
      const active = path === match || path.startsWith(`${match}/`);
      if (active) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    }
  }

  return { root, main, setActive };
}
