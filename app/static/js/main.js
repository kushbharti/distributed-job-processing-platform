import { ApiError } from "./api.js";
import { currentUser, signOut } from "./auth.js";
import { APP_NAME } from "./config.js";
import { navigate, route, start } from "./router.js";
import { isSignedIn, onSessionChange } from "./session.js";
import { h } from "./ui/dom.js";
import { createShell } from "./ui/shell.js";

const root = document.getElementById("app");
let shell = null;

// Routes. Pages load on first visit. "auth" pages use the full-screen layout; the rest sit in the shell.
route("/login", () => import("./pages/login.js"), {
  layout: "auth",
  guestOnly: true,
});
route("/register", () => import("./pages/register.js"), {
  layout: "auth",
  guestOnly: true,
});
route("/documents", () => import("./pages/documents.js"));

function focusPage(container, page) {
  const target = page.focus ?? container.querySelector("h1");
  if (!target) return;
  if (!target.matches("input, textarea, select, button, a[href]"))
    target.tabIndex = -1;
  target.focus({ preventScroll: true });
}

async function render(layout, page, path) {
  document.title = page.title ? `${page.title} - ${APP_NAME}` : APP_NAME;

  if (layout === "app") {
    if (!shell) {
      const user = await currentUser().catch(() => null);
      shell = createShell({
        email: user?.email ?? "",
        onSignOut: handleSignOut,
      });
      root.replaceChildren(shell.root);
    }
    shell.main.replaceChildren(page.node);
    shell.setActive(path);
    focusPage(shell.main, page);
  } else {
    shell = null;
    root.replaceChildren(page.node);
    focusPage(root, page);
  }
  window.scrollTo(0, 0);
}

async function handleSignOut() {
  await signOut();
  shell = null;
  navigate("/login", { replace: true });
}

function notFoundPage(path) {
  return {
    title: "Page not found",
    node: h(
      "div",
      {},
      h(
        "div",
        { class: "page__head" },
        h("h1", {}, "Page not found"),
        h("p", { class: "page__sub" }, `Nothing lives at ${path}.`),
      ),
      h(
        "a",
        { class: "btn btn--secondary", href: "#/documents" },
        "Back to documents",
      ),
    ),
  };
}

function errorPage(error, retry) {
  if (!(error instanceof ApiError)) console.error(error);
  const message =
    error instanceof ApiError
      ? error.message
      : "Something went wrong while loading this page.";
  return {
    title: "Couldn't load page",
    node: h(
      "div",
      {},
      h(
        "div",
        { class: "page__head" },
        h("h1", {}, "This page didn't load"),
        h("p", { class: "page__sub" }, message),
      ),
      h(
        "button",
        { type: "button", class: "btn btn--secondary", onclick: retry },
        "Try again",
      ),
    ),
  };
}

// The server rejected our token: go back to sign-in and say why.
onSessionChange(({ reason }) => {
  if (reason === "expired") navigate("/login?expired=1", { replace: true });
});

// The skip link would normally change the URL hash, which is our router's input.
document.getElementById("skip-link").addEventListener("click", (event) => {
  event.preventDefault();
  document.getElementById("main")?.focus();
});

start({ isSignedIn, render, notFound: notFoundPage, errorPage });
