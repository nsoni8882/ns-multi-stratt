import { beforeEach, describe, expect, it, vi } from "vitest";
import { asReport, clear, installGlobalHandlers, read, record } from "./errorLog";

describe("errorLog", () => {
  beforeEach(() => clear());

  it("keeps the newest error first", () => {
    record({ source: "window", message: "first" });
    record({ source: "window", message: "second" });
    expect(read().map((e) => e.message)).toEqual(["second", "first"]);
  });

  it("keeps at most ten, so a loop cannot fill storage", () => {
    for (let i = 0; i < 25; i++) record({ source: "render", message: `e${i}` });
    const kept = read();
    expect(kept).toHaveLength(10);
    expect(kept[0].message).toBe("e24");
  });

  it("truncates a huge stack", () => {
    record({ source: "render", message: "big", stack: "x".repeat(5000) });
    expect(read()[0].stack).toHaveLength(2000);
  });

  it("survives storage being unavailable", () => {
    const spy = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(() => record({ source: "window", message: "nope" })).not.toThrow();
    spy.mockRestore();
  });

  it("treats unparseable storage as empty rather than throwing", () => {
    window.localStorage.setItem("errors", "{not json");
    expect(read()).toEqual([]);
  });

  it("builds a pasteable report", () => {
    record({ source: "promise", message: "fetch failed", stack: "at getChart" });
    const report = asReport(read(), "TestBrowser/1.0");
    expect(report).toContain("1 error · TestBrowser/1.0");
    expect(report).toContain("fetch failed");
    expect(report).toContain("at getChart");
  });

  it("records an uncaught error and an unhandled rejection", () => {
    const uninstall = installGlobalHandlers(window);
    window.dispatchEvent(new ErrorEvent("error", { message: "boom", error: new Error("boom") }));
    const rejection = new Event("unhandledrejection") as Event & { reason?: unknown };
    rejection.reason = new Error("promise died");
    window.dispatchEvent(rejection);
    expect(read().map((e) => [e.source, e.message])).toEqual([
      ["promise", "promise died"],
      ["window", "boom"],
    ]);
    // Checked through removeEventListener rather than by firing another error: an ErrorEvent
    // nothing handles becomes an uncaught exception and fails the run.
    const off = vi.spyOn(window, "removeEventListener");
    uninstall();
    expect(off).toHaveBeenCalledWith("error", expect.any(Function));
    expect(off).toHaveBeenCalledWith("unhandledrejection", expect.any(Function));
    off.mockRestore();
  });
});
