import { api } from "./api.js";
import { clearToken, setToken } from "./session.js";

let cachedUser = null;

export async function signIn(email, password) {
  // FastAPI's OAuth2 form calls the email field "username"
  const data = await api("/auth/login", {
    method: "POST",
    form: { username: email, password },
    auth: false,
  });
  cachedUser = null;
  setToken(data.access_token);
}

export async function register(email, password) {
  await api("/auth/register", {
    method: "POST",
    json: { email, password },
    auth: false,
  });
}

export async function currentUser() {
  if (!cachedUser) cachedUser = await api("/auth/me");
  return cachedUser;
}

export async function signOut() {
  try {
    // Puts the token on the server's denylist so it stops working everywhere
    await api("/auth/logout", { method: "POST", handle401: false });
  } catch {
    /* Even if this fails, we forget the token here; it expires on its own anyway. */
  }
  cachedUser = null;
  clearToken();
}
