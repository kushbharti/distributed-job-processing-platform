// Re-runs `task` every few seconds while `shouldContinue()` is true. It pauses while the tab
// is hidden, resumes with an immediate refresh when it comes back, and never overlaps itself.
export function createPoller({ task, shouldContinue, intervalMs = 4000 }) {
  let timer = null;
  let stopped = false;

  const clear = () => {
    clearTimeout(timer);
    timer = null;
  };

  async function runOnce() {
    try {
      await task();
    } catch {
      /* a failed refresh is not worth interrupting the person; the next one tries again */
    }
    schedule();
  }

  function schedule() {
    clear();
    if (stopped || document.hidden || !shouldContinue()) return;
    timer = setTimeout(runOnce, intervalMs);
  }

  function onVisibilityChange() {
    if (stopped || document.hidden || !shouldContinue()) return;
    clear();
    runOnce();
  }

  document.addEventListener("visibilitychange", onVisibilityChange);

  return {
    schedule,
    stop() {
      stopped = true;
      clear();
      document.removeEventListener("visibilitychange", onVisibilityChange);
    },
  };
}
