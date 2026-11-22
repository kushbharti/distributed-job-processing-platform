import { expireSession, getToken } from "./session.js";

const BASE = "/api/v1";

export class ApiError extends Error {
  constructor(status, message, data = null) {
    super(message);
    this.name = "ApiError";
    this.status = status; // 0 means the server could not be reached
    this.data = data;
  }
}

function messageFrom(status, data) {
  const detail = data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length)
    return detail.map((item) => item.msg).join(" ");
  if (status >= 500) return "The server hit a problem. Try again in a moment.";
  if (status === 404) return "That wasn't found.";
  return `The request failed (${status}).`;
}

// Text that is safe to show a person, whatever was thrown.
export function userMessage(error) {
  return error instanceof ApiError
    ? error.message
    : "Something went wrong. Try again.";
}

export async function api(
  path,
  {
    method = "GET",
    json,
    form,
    body,
    headers,
    auth = true,
    handle401 = true,
    signal,
  } = {},
) {
  const requestHeaders = new Headers(headers);
  let payload = body;

  if (json !== undefined) {
    requestHeaders.set("Content-Type", "application/json");
    payload = JSON.stringify(json);
  } else if (form !== undefined) {
    payload = new URLSearchParams(form); // the browser sets the form content type itself
  }

  if (auth) {
    const token = getToken();
    if (token) requestHeaders.set("Authorization", `Bearer ${token}`);
  }

  let response;
  try {
    response = await fetch(`${BASE}${path}`, {
      method,
      headers: requestHeaders,
      body: payload,
      signal,
    });
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new ApiError(
      0,
      "Can't reach the server. Check your connection and try again.",
    );
  }

  if (response.status === 204) return null;

  const isJson = (response.headers.get("content-type") ?? "").includes(
    "application/json",
  );
  const data = isJson ? await response.json().catch(() => null) : null;

  if (response.ok) return data;

  // A token we sent was rejected: the session is over. (The login call opts out, because
  // a 401 there just means "wrong password".)
  if (response.status === 401 && auth && handle401) expireSession();

  throw new ApiError(response.status, messageFrom(response.status, data), data);
}
