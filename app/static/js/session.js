// Where the access token lives, and how the rest of the app hears about session changes.
// sessionStorage clears when the tab closes. Anything that can run script on this page
// can read it, which is why the site never inserts server text as HTML.

const KEY = "docket.token";
const listeners = new Set();

function notify(reason) {
  for (const listener of listeners) listener({ reason });
}

function readPayload(token) {
  try {
    const part = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(part));
  } catch {
    return null;
  }
}

export function getToken() {
  try {
    return sessionStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function setToken(token) {
  try {
    sessionStorage.setItem(KEY, token);
  } catch {
    /* storage blocked: the user simply has to sign in again after a reload */
  }
  notify("signed-in");
}

export function clearToken(reason = "signed-out") {
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    /* nothing to remove */
  }
  notify(reason);
}

export function isSignedIn() {
  const token = getToken();
  if (!token) return false;
  const exp = readPayload(token)?.exp;
  if (exp && exp * 1000 <= Date.now()) {
    // Expired while the tab sat idle: drop it quietly; the router sends the user to sign in.
    try {
      sessionStorage.removeItem(KEY);
    } catch {
      /* nothing to remove */
    }
    return false;
  }
  return true;
}

// Called when the server rejects a token that we still hold.
export function expireSession() {
  if (!getToken()) return;
  clearToken("expired");
}

export function onSessionChange(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
