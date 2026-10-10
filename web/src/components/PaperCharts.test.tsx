import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, test, vi } from "vitest";
import * as api from "../api";
import { chart as chartFile, paperTradingFile, strategies } from "../test-fixtures";
import { marksForDates } from "../lib/chartMarks";
import { PaperCharts } from "./PaperCharts";

const f = paperTradingFile;

function show(props = {}) {
  vi.spyOn(api, "getChart").mockResolvedValue(chartFile);
  return render(
    <PaperCharts symbols={f.symbols} positions={f.positions} trades={f.trades}
                 strategies={strategies.strategies} {...props} />,
  );
}

test("one tile per traded symbol", () => {
  show();
  expect(screen.getByRole("button", { name: /AMZN chart/i })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /AAPL chart/i })).toBeInTheDocument();
});

test("a tile says whether that name is held", () => {
  show();
  expect(screen.getByRole("button", { name: /AAPL chart/i })).toHaveTextContent(/held/i);
  expect(screen.getByRole("button", { name: /AMZN chart/i })).toHaveTextContent(/flat/i);
});

test("clicking a tile opens the chart overlay for that symbol", async () => {
  show();
  await userEvent.click(screen.getByRole("button", { name: /AMZN chart/i }));
  expect(await screen.findByRole("dialog", { name: /AMZN chart/i })).toBeInTheDocument();
});

test("the overlay uses the MACD + RSI Reversal indicator setup", async () => {
  show();
  await userEvent.click(screen.getByRole("button", { name: /AMZN chart/i }));
  await screen.findByRole("dialog");
  // getChart is called for the daily bars; the config comes from the shipped strategy entry
  // rather than being copied, so the two cannot drift apart.
  expect(api.getChart).toHaveBeenCalledWith("1d", "AMZN");
});

describe("marksForDates", () => {
  const bars: [number, number, number, number, number, number][] = [
    [1760227200, 1, 2, 0.5, 1.5, 100],
    [1760313600, 1, 2, 0.5, 1.5, 100],
    [1760400000, 1, 2, 0.5, 1.5, 100],
  ];
  // Derived from the bars rather than written out, so the two cannot drift apart.
  const [d0, d1, d2] = bars.map(([t]) => new Date(t * 1000).toISOString().slice(0, 10));

  it("maps a trade's entry and exit dates onto the bars they happened on", () => {
    expect(marksForDates(bars, [{ entry_date: d0, exit_date: d2 }])).toEqual([
      { side: "BUY", bar_time: bars[0][0] },
      { side: "SELL", bar_time: bars[2][0] },
    ]);
  });

  it("marks an open position's entry with no exit", () => {
    expect(marksForDates(bars, [{ entry_date: d1, exit_date: null }]))
      .toEqual([{ side: "BUY", bar_time: bars[1][0] }]);
  });

  it("drops a date with no matching bar rather than guessing one", () => {
    expect(marksForDates(bars, [{ entry_date: "2020-01-01", exit_date: null }])).toEqual([]);
  });

  it("handles an empty trade list", () => {
    expect(marksForDates(bars, [])).toEqual([]);
  });
});
