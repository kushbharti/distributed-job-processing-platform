// A small hash router: "#/jobs/123" matches the route "/jobs/:id".

const routes = [];
let config = null;
let navigationId = 0;
let currentCleanup = null;

export function route(
  pattern,
  loader,
  { layout = "app", guestOnly = false } = {},
) {
  const keys = [];
  const source = pattern.replace(/:([A-Za-z]+)/g, (_, key) => {
    keys.push(key);
    return "([^/]+)";
  });
  routes.push({
    regex: new RegExp(`^${source}$`),
    keys,
    loader,
    layout,
    guestOnly,
  });
}

export function navigate(path, { replace = false } = {}) {
  const target = `#${path}`;
  if (location.hash === target) {
    handle();
    return;
  }
  if (replace) location.replace(target);
  else location.hash = path;
}

function currentLocation() {
  const raw = location.hash.slice(1) || "/";
  const [path, search = ""] = raw.split("?");
  return { path: path || "/", query: new URLSearchParams(search) };
}

function safeDecode(value) {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

function findRoute(path) {
  for (const candidate of routes) {
    const match = candidate.regex.exec(path);
    if (!match) continue;
    const params = {};
    candidate.keys.forEach((key, index) => {
      params[key] = safeDecode(match[index + 1]);
    });
    return { route: candidate, params };
  }
  return null;
}

async function commit(id, layout, page, path) {
  if (id !== navigationId) {
    // The user navigated again while this page was loading: discard it.
    page.cleanup?.();
    return;
  }
  currentCleanup?.();
  currentCleanup = page.cleanup ?? null;
  await config.render(layout, page, path);
}

async function handle() {
  const id = ++navigationId;
  const { path, query } = currentLocation();
  const signedIn = config.isSignedIn();

  if (path === "/") {
    navigate(signedIn ? "/documents" : "/login", { replace: true });
    return;
  }

  const found = findRoute(path);

  if (!found) {
    if (!signedIn) {
      navigate("/login", { replace: true });
      return;
    }
    await commit(id, "app", config.notFound(path), path);
    return;
  }

  if (!found.route.guestOnly && !signedIn) {
    navigate(`/login?next=${encodeURIComponent(path)}`, { replace: true });
    return;
  }
  if (found.route.guestOnly && signedIn) {
    navigate("/documents", { replace: true });
    return;
  }

  let page;
  try {
    const module = await found.route.loader();
    page = await module.default({ params: found.params, query });
  } catch (error) {
    page = config.errorPage(error, handle);
  }
  await commit(id, found.route.layout, page, path);
}

export function start(options) {
  config = options;
  window.addEventListener("hashchange", handle);
  return handle();
}
