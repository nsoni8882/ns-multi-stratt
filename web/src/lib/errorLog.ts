/**
 * A ring buffer of browser errors, kept in localStorage.
 *
 * There is no server to send these to — the site is static files on GitHub Pages — so an error
 * that happens in someone's browser leaves no trace anywhere unless the page keeps it itself.
 * This keeps the last few, survives a reload, and the footer offers them as copyable text, so
 * "the site broke" can become an actual stack trace without a telemetry service.
 *
 * Every read and write is wrapped: storage throws in private mode and in some embedded
 * webviews, and an error logger that throws while logging an error is worse than none.
 */
const KEY = "errors";
const MAX = 10; // enough to see a repeating failure, small enough never to matter for quota

export interface LoggedError {
  at: string; // ISO timestamp
  message: string;
  source: "render" | "window" | "promise";
  stack?: string;
  url: string;
}

export function record(entry: Omit<LoggedError, "at" | "url">): LoggedError {
  const full: LoggedError = {
    ...entry,
    at: new Date().toISOString(),
    url: typeof location === "undefined" ? "" : location.hash || location.pathname,
    stack: entry.stack?.slice(0, 2000), // a full React stack can be enormous
  };
  try {
    const kept = [full, ...read()].slice(0, MAX);
    window.localStorage.setItem(KEY, JSON.stringify(kept));
  } catch {
    /* storage blocked or full: the console still has it */
  }
  return full;
}

export function read(): LoggedError[] {
  try {
    const raw = window.localStorage.getItem(KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((e) => e && typeof e.message === "string") : [];
  } catch {
    return []; // unparseable or unavailable is the same as empty
  }
}

export function clear(): void {
  try {
    window.localStorage.removeItem(KEY);
  } catch {
    /* nothing to do */
  }
}

/** One blob to paste into a bug report. Plain text on purpose: it has to survive a chat box. */
export function asReport(errors: LoggedError[], buildInfo = ""): string {
  const head = `${errors.length} error${errors.length === 1 ? "" : "s"}${buildInfo ? ` · ${buildInfo}` : ""}`;
  return [head, ...errors.map((e) =>
    `\n[${e.at}] ${e.source} at ${e.url}\n${e.message}${e.stack ? `\n${e.stack}` : ""}`,
  )].join("\n");
}

/** Catches what React cannot: errors outside render, and rejected promises with no handler. */
export function installGlobalHandlers(target: Window = window): () => void {
  const onError = (e: ErrorEvent) => {
    record({ source: "window", message: e.message || String(e.error), stack: e.error?.stack });
  };
  const onRejection = (e: PromiseRejectionEvent) => {
    const r = e.reason;
    record({
      source: "promise",
      message: r instanceof Error ? r.message : String(r),
      stack: r instanceof Error ? r.stack : undefined,
    });
  };
  target.addEventListener("error", onError);
  target.addEventListener("unhandledrejection", onRejection);
  return () => {
    target.removeEventListener("error", onError);
    target.removeEventListener("unhandledrejection", onRejection);
  };
}
