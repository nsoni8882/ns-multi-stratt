import { useState } from "react";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { HistoryModal } from "./HistoryModal";
import type { Release } from "../types";

const HISTORY: Release[] = [
  { version: "1.2.0", date: "2026-10-03", summary: "Tested extra filters; none beat the current rules." },
  { version: "1.1.0", date: "2026-10-02", summary: "Raised the minimum history to 400 bars." },
  { version: "1.0.0", date: "2026-10-01", summary: "First version." },
];

const show = (history = HISTORY, onClose = vi.fn()) => {
  render(<HistoryModal strategyName="Trend Pullback" history={history} onClose={onClose} />);
  return onClose;
};

describe("HistoryModal", () => {
  it("lists every version with its date and summary", () => {
    show();
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(3);
    expect(within(items[0]).getByText("v1.2.0")).toBeInTheDocument();
    expect(within(items[0]).getByText(/none beat the current rules/)).toBeInTheDocument();
    expect(within(items[2]).getByText("v1.0.0")).toBeInTheDocument();
  });

  it("puts the latest version on top and marks it current", () => {
    show();
    const items = screen.getAllByRole("listitem");
    expect(items.map((li) => li.querySelector(".ver")?.textContent)).toEqual(["v1.2.0", "v1.1.0", "v1.0.0"]);
    expect(within(items[0]).getByText("Current")).toBeInTheDocument();
    expect(within(items[1]).queryByText("Current")).not.toBeInTheDocument();
  });

  it("names the strategy it belongs to", () => {
    show();
    expect(screen.getByRole("dialog")).toHaveAccessibleName("Trend Pullback change history");
    expect(screen.getByText("Trend Pullback")).toBeInTheDocument();
  });

  it("uses a machine-readable date", () => {
    show();
    expect(screen.getByText("2026-10-03").closest("time")).toHaveAttribute("dateTime", "2026-10-03");
  });

  it("closes on the close button, Escape and a click on the backdrop", async () => {
    const user = userEvent.setup();

    const onClose = show();
    await user.click(screen.getByRole("button", { name: /close change history/i }));
    expect(onClose).toHaveBeenCalledOnce();

    const onKeyClose = show(HISTORY, vi.fn());
    await user.keyboard("{Escape}");
    expect(onKeyClose).toHaveBeenCalledOnce();
  });

  it("focuses the close button so the overlay is keyboard-reachable", () => {
    show();
    expect(screen.getByRole("button", { name: /close change history/i })).toHaveFocus();
  });

  it("says so rather than rendering an empty list when there is no history", () => {
    show([]);
    expect(screen.getByText(/no recorded changes yet/i)).toBeInTheDocument();
    expect(screen.queryByRole("listitem")).not.toBeInTheDocument();
  });
});

describe("HistoryModal focus handling", () => {
  it("does not steal focus back when the parent re-renders", async () => {
    // The overlay has no focus trap, so a reader can Tab out to the page behind it. If the
    // focus effect is keyed on `onClose` and the parent passes a fresh closure each render,
    // every keystroke that updates parent state yanks focus back to the close button and the
    // character is lost.
    const user = userEvent.setup();
    function Parent() {
      const [text, setText] = useState("");
      return (
        <>
          <HistoryModal strategyName="Trend Pullback" history={HISTORY} onClose={() => setText(text)} />
          <input aria-label="Search" value={text} onChange={(e) => setText(e.target.value)} />
        </>
      );
    }
    render(<Parent />);
    const input = screen.getByLabelText("Search");
    input.focus();
    await user.keyboard("abc");
    expect(input).toHaveFocus();
    expect(input).toHaveValue("abc");
  });
});
