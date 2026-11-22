import { h } from "./dom.js";

export function watchConnectivity() {
  const region = h("div", { role: "status" });
  document.body.insertBefore(region, document.getElementById("app"));

  const update = () => {
    region.replaceChildren(
      navigator.onLine
        ? []
        : h(
            "p",
            { class: "offline-banner" },
            "You're offline. Pages will work again once you reconnect.",
          ),
    );
  };

  window.addEventListener("online", update);
  window.addEventListener("offline", update);
  update();
}
