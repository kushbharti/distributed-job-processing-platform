import { APP_NAME } from "../config.js";
import { h } from "./dom.js";
import { pipeline } from "./pipeline.js";

// The two-part layout shared by sign-in and registration: the form, and what the site does.
export function authScreen({ title, form, footer }) {
  return h(
    "main",
    { id: "main", class: "auth", tabindex: "-1" },
    h(
      "section",
      { class: "auth__panel" },
      h(
        "a",
        { class: "brand", href: "#/login" },
        h("img", {
          src: "/static/favicon.svg",
          alt: "",
          width: "24",
          height: "24",
        }),
        APP_NAME,
      ),
      h("h1", { class: "auth__title" }, title),
      form,
      h("p", { class: "auth__footer" }, footer),
    ),
    h(
      "section",
      { class: "auth__intro" },
      h(
        "p",
        { class: "auth__lede" },
        "Upload a PDF. A summary and a report come back.",
      ),
      h(
        "p",
        { class: "auth__copy" },
        "Processing runs in the background, so you can close the tab and return when it's finished.",
      ),
      h(
        "p",
        { class: "auth__copy" },
        "Every file goes through the same seven steps:",
      ),
      pipeline({ intro: true, label: "What happens to your file" }),
      h("p", { class: "auth__note" }, "Documents are private to your account."),
    ),
  );
}
