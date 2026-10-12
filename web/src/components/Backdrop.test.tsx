import { render, screen, waitFor } from "@testing-library/react";
import { Backdrop } from "./Backdrop";

afterEach(() => vi.unstubAllGlobals());

describe("the ambient backdrop", () => {
  it("is drawn behind the page, out of reach of the pointer and the screen reader", async () => {
    render(<Backdrop />);
    const layer = await screen.findByTestId("backdrop");
    expect(layer).toHaveAttribute("aria-hidden", "true");
    // Decoration must not be announced, clicked, or tabbed to; the CSS handles the rest.
    expect(layer.querySelectorAll("a, button, input")).toHaveLength(0);
  });

  it("is skipped entirely when the visitor has asked for less data", async () => {
    vi.stubGlobal("navigator", Object.create(navigator, { connection: { value: { saveData: true } } }));
    render(<Backdrop />);
    await waitFor(() => expect(screen.queryByTestId("backdrop")).not.toBeInTheDocument());
  });

  it("is skipped on a 2G connection, where three compositor layers cost battery", async () => {
    vi.stubGlobal("navigator", Object.create(navigator, { connection: { value: { effectiveType: "2g" } } }));
    render(<Backdrop />);
    await waitFor(() => expect(screen.queryByTestId("backdrop")).not.toBeInTheDocument());
  });
});
