import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ErrorBoundary } from "./ErrorBoundary";
import { ErrorFooter } from "./ErrorFooter";
import { FailingTestsNote } from "./Feedback";
import { clear, read } from "../lib/errorLog";

function Boom(): never {
  throw new Error("chart exploded");
}

describe("ErrorBoundary", () => {
  beforeEach(() => {
    clear();
    // React logs the caught error; the test does not need the noise.
    vi.spyOn(console, "error").mockImplementation(() => {});
  });
  afterEach(() => vi.restoreAllMocks());

  it("shows a message instead of a blank page, and says the data is unaffected", () => {
    render(<ErrorBoundary><Boom /></ErrorBoundary>);
    expect(screen.getByRole("alert")).toHaveTextContent("hit an error and stopped");
    expect(screen.getByRole("alert")).toHaveTextContent("signal data itself is fine");
  });

  it("records the error so it can be copied out of the footer", () => {
    render(<ErrorBoundary><Boom /></ErrorBoundary>);
    const logged = read();
    expect(logged[0].message).toBe("chart exploded");
    expect(logged[0].source).toBe("render");
  });

  it("renders its children when nothing is wrong", () => {
    render(<ErrorBoundary><p>fine</p></ErrorBoundary>);
    expect(screen.getByText("fine")).toBeInTheDocument();
  });
});

describe("ErrorFooter", () => {
  beforeEach(() => clear());

  it("shows nothing until something has gone wrong", () => {
    const { container } = render(<ErrorFooter errors={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("offers the details once an error exists", () => {
    render(<ErrorFooter errors={[{ at: "2026-10-03T18:00:00Z", message: "boom", source: "window", url: "#/" }]} />);
    expect(screen.getByText(/1 error happened in your browser/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Copy details" })).toBeInTheDocument();
  });
});

describe("ErrorFooter reporting", () => {
  it("offers a prefilled issue, since nothing collects errors automatically", () => {
    render(<ErrorFooter errors={[{ at: "2026-10-03T18:00:00Z", message: "chart exploded", source: "render", url: "#/strategy/trend-pullback" }]} />);
    const link = screen.getByRole("link", { name: "Report" });
    const href = link.getAttribute("href") ?? "";
    expect(href).toContain("github.com/nsoni8882/ns-multi-stratt/issues/new");
    expect(decodeURIComponent(href)).toContain("Site error: chart exploded");
    expect(decodeURIComponent(href)).toContain("#/strategy/trend-pullback");
  });
});

describe("FailingTestsNote", () => {
  it("says nothing when the build's tests passed", () => {
    const { container } = render(<FailingTestsNote tests={{ python: "success", web: "success" }} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("says nothing when there is no health record at all", () => {
    const { container } = render(<FailingTestsNote />);
    expect(container).toBeEmptyDOMElement();
  });

  it("names the suite that failed", () => {
    render(<FailingTestsNote tests={{ python: "failure", web: "success" }} />);
    expect(screen.getByRole("status")).toHaveTextContent("failing tests (python)");
  });

  it("does not treat a step that never ran as a failure", () => {
    const { container } = render(<FailingTestsNote tests={{ python: "not run" }} />);
    expect(container).toBeEmptyDOMElement();
  });
});
