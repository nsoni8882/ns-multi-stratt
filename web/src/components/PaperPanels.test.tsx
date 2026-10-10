import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { paperTradingFile } from "../test-fixtures";
import { PaperBalance } from "./PaperBalance";
import { PaperEquityCurve } from "./PaperEquityCurve";
import { PaperPositions } from "./PaperPositions";
import { PaperRuns } from "./PaperRuns";
import { PaperSignalRows } from "./PaperSignalRows";
import { PaperTrades } from "./PaperTrades";

const f = paperTradingFile;

test("balance shows all five figures with the P/L signed", () => {
  render(<PaperBalance account={f.account} />);
  expect(screen.getByText("Opening balance")).toBeInTheDocument();
  expect(screen.getByText("$100,000")).toBeInTheDocument();
  // +$592 is both the total and the unrealised figure in this fixture, so scope to the cell.
  expect(screen.getAllByText(/\+\$592/).length).toBeGreaterThan(0);
  expect(screen.getByText(/49\.5%/)).toBeInTheDocument();
});

test("a negative total P/L is coloured as a loss and carries its sign", () => {
  render(<PaperBalance account={{ ...f.account, total_pl: -1234, total_pl_pct: -1.23 }} />);
  expect(screen.getByText(/-\$1,234/).className).toMatch(/sell/);
});

test("equity curve draws a path and marks the in-position days", () => {
  const { container } = render(<PaperEquityCurve curve={f.equity_curve} opening={100000} />);
  expect(container.querySelector("path")).toBeTruthy();
  expect(container.querySelectorAll("rect").length).toBeGreaterThan(0);
});

test("an empty equity curve renders an explanation, not an empty box", () => {
  render(<PaperEquityCurve curve={[]} opening={100000} />);
  expect(screen.getByText(/no history yet/i)).toBeInTheDocument();
});

test("a position shows its bars-held meter accessibly", () => {
  render(<PaperPositions positions={f.positions} />);
  expect(screen.getByText("AAPL")).toBeInTheDocument();
  expect(screen.getByRole("progressbar")).toHaveAccessibleName(/4 of 10 bars/i);
});

test("no open positions explains the idleness instead of showing nothing", () => {
  render(<PaperPositions positions={[]} />);
  expect(screen.getByText(/flat/i)).toBeInTheDocument();
  expect(screen.getByText(/13%/)).toBeInTheDocument();
});

test("signal state shows the threshold each symbol is measured against", () => {
  render(<PaperSignalRows state={f.signal_state} />);
  expect(screen.getByText("Waiting")).toBeInTheDocument();
  expect(screen.getByText("Held")).toBeInTheDocument();
  expect(screen.getAllByText(/10/).length).toBeGreaterThan(0);
});

test("a blocked trend gate is named as such", () => {
  render(<PaperSignalRows state={[{ ...f.signal_state[0], verdict: "Trend gate blocked",
                                    trend_gap_pct: -3.2 }]} />);
  expect(screen.getByText("Trend gate blocked")).toBeInTheDocument();
});

test("no trades yet says how many are needed and gives no verdict", () => {
  render(<PaperTrades trades={[]} evaluation={f.evaluation} />);
  expect(screen.getByText(/0 of 30/)).toBeInTheDocument();
  expect(screen.queryByText(/verdict/i)).not.toBeInTheDocument();
});

test("a closed round trip shows its exit reason and P/L", () => {
  const trade = { symbol: "AMZN", entry_date: "2026-10-12", entry_price: 100,
                  exit_date: "2026-10-15", exit_price: 103, qty: 100, bars_held: 3,
                  exit_reason: "rsi", pl: 300, pl_pct: 3, slippage_bps: 0,
                  rules_version: "512f04ab1a78" };
  render(<PaperTrades trades={[trade]} evaluation={{ ...f.evaluation, trades_closed: 1,
                                                     bps_per_trade: 300, win_rate: 100,
                                                     mean_bars_held: 3 }} />);
  expect(screen.getByText("RSI exit")).toBeInTheDocument();
  expect(screen.getByText(/\+3\.00%/)).toBeInTheDocument();
  expect(screen.getByText(/150\.1/)).toBeInTheDocument();
});

test("a time-stopped exit is labelled in plain English", () => {
  const trade = { symbol: "AAPL", entry_date: "2026-10-01", entry_price: 100,
                  exit_date: "2026-10-15", exit_price: 99, qty: 10, bars_held: 10,
                  exit_reason: "time_stop", pl: -10, pl_pct: -1, slippage_bps: null,
                  rules_version: "512f04ab1a78" };
  render(<PaperTrades trades={[trade]} evaluation={f.evaluation} />);
  expect(screen.getByText("Time stop")).toBeInTheDocument();
});

test("a missing value renders an em dash with an explanation, never a literal double hyphen", () => {
  const trade = { symbol: "AAPL", entry_date: null, entry_price: 100, exit_date: null,
                  exit_price: 0, qty: null, bars_held: null, exit_reason: null, pl: 0,
                  pl_pct: null, slippage_bps: null, rules_version: null };
  const { container } = render(<PaperTrades trades={[trade]} evaluation={f.evaluation} />);
  expect(container.textContent).not.toContain("--");
  expect(container.textContent).toContain("—");
});

test("the run log lists the last runs and what each decided", () => {
  render(<PaperRuns runs={f.runs} />);
  expect(screen.getByText(/1 order/)).toBeInTheDocument();
});

test("a missed or late run is announced", () => {
  render(<PaperRuns runs={[{ ...f.runs[0], late: true, skip_reason: "inside the cutoff" }]} />);
  expect(screen.getByRole("status", { name: "Last run warning" }))
    .toHaveTextContent(/cutoff/i);
});
