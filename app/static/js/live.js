import { getToken } from "./session.js";

export function watchJob(jobId, { onMessage, onStatus }) {
  let socket = null;
  let timer = null;
  let attempt = 0;
  let closed = false;

  function connect() {
    if (closed) return;
    onStatus("connecting");

    const scheme = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(
      `${scheme}://${location.host}/api/v1/ws/jobs/${encodeURIComponent(jobId)}`,
    );
    socket = ws;
    let received = false;

    ws.addEventListener("open", () => {
      const token = getToken();
      if (!token) {
        closed = true;
        ws.close();
        onStatus("unauthorized");
        return;
      }
      // The token travels in a message, not in the URL, so it never ends up in server logs.
      ws.send(JSON.stringify({ type: "auth", token }));
    });

    ws.addEventListener("message", (event) => {
      let message;
      try {
        message = JSON.parse(event.data);
      } catch {
        return;
      }
      if (!received) {
        received = true;
        attempt = 0;
        onStatus("live");
      }
      onMessage(message);
    });

    ws.addEventListener("close", (event) => {
      if (socket !== ws) return;
      socket = null;
      if (closed) return;

      if (event.code === 1000) return onStatus("closed"); // the job finished
      if (event.code === 1008) return onStatus("unavailable"); // too many open connections
      if (event.code === 4401) return onStatus("unauthorized"); // bad or expired token
      if (event.code === 4404) return onStatus("missing"); // no such job

      onStatus("disconnected");
      const delay = Math.min(1000 * 2 ** attempt, 15000) + Math.random() * 500;
      attempt += 1;
      timer = setTimeout(connect, delay);
    });
  }

  connect();

  return {
    close() {
      closed = true;
      clearTimeout(timer);
      if (socket) {
        const ws = socket;
        socket = null;
        ws.close(1000);
      }
    },
  };
}
