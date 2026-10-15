import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HashRouter } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";
import * as api from "../api";
import { labFixture } from "../lab-fixture";
import { StrategiesProvider } from "../strategiesContext";
import { market, strategies } from "../test-fixtures";
import type { LabFile } from "../types";
import { LabPage } from "./LabPage";

function show(file: LabFile | Error = labFixture()) {
  vi.spyOn(api, "getStrategies").mockResolvedValue(strategies);
  vi.spyOn(api, "getMarket").mockResolvedValue(market);
  vi.spyOn(api, "getHealth").mockRejectedValue(new Error("not needed"));
  if (file instanceof Error) vi.spyOn(api, "getLab").mockRejectedValue(file);
  else vi.spyOn(api, "getLab").mockResolvedValue(file);
  window.location.hash = "#/lab";
  return render(<HashRouter><StrategiesProvider><LabPage /></StrategiesProvider></HashRouter>);
}

beforeEach(() => {
  api.clearCache();
  vi.restoreAllMocks();
});

test("the hero says how many ideas were tried and how high the bar is", async () => {
  show();
  expect(await screen.findByText("Intraday Lab")).toBeInTheDocument();
  expect(screen.getByText("Paper money")).toBeInTheDocument();
  const bar = screen.getByLabelText(/how hard the bar/i);
  expect(bar).toHaveTextContent(/25.*ideas tried/);
  expect(bar).toHaveTextContent(/t ≥ 2\.50/);
});

test("the pipeline counts every stage and a chip filters the cards", async () => {
  show();
  const nav = await screen.findByRole("navigation", { name: /where ideas are/i });
  expect(within(nav).getByRole("button", { name: /shadow/i })).toHaveTextContent("1");
  expect(within(nav).getByRole("button", { name: /rejected/i })).toHaveTextContent("2");
  expect(screen.getAllByRole("article")).toHaveLength(5);
  await userEvent.click(within(nav).getByRole("button", { name: /rejected/i }));
  expect(screen.getAllByRole("article")).toHaveLength(2);
  await userEvent.click(within(nav).getByRole("button", { name: /rejected/i }));
  expect(screen.getAllByRole("article")).toHaveLength(5);
});

test("a failed strategy's checklist names what failed, with glyphs not just colour", async () => {
  show();
  const card = (await screen.findByRole("article", { name: /VWAP stretch reversion/i }));
  const failed = within(card).getByText(/Survives doubled costs/).closest("li")!;
  expect(failed.className).toBe("no");
  expect(failed).toHaveTextContent("✕");
  expect(failed).toHaveTextContent(/failed/);
  const holdout = within(card).getByText(/Sealed holdout/).closest("li")!;
  expect(holdout).toHaveTextContent(/not opened/);
});

test("the shadow strategy shows its failure rules as progress toward applying", async () => {
  show();
  const card = (await screen.findByRole("article", { name: /stocks in play/i }));
  const meters = within(card).getAllByRole("progressbar");
  expect(meters).toHaveLength(2);
  expect(meters[0]).toHaveAccessibleName(/0 of 30 trades/);
});

test("the headline figures come from the selected strategy", async () => {
  show();
  const kpis = await screen.findByRole("region", { name: /key figures/i });
  expect(within(kpis).getByText("Net P&L")).toBeInTheDocument();
  expect(kpis).toHaveTextContent(/Opening-range breakout, stocks in play/);
  const vwap = screen.getByRole("article", { name: /VWAP stretch reversion/i });
  await userEvent.click(within(vwap).getByRole("button", { name: /show performance/i }));
  expect(screen.getByRole("region", { name: /key figures/i })).toHaveTextContent(/VWAP stretch reversion/);
  expect(within(vwap).getByRole("button", { name: /showing above/i })).toBeInTheDocument();
});

test("the trade table filters, sorts, pages and expands a row", async () => {
  show();
  const section = await screen.findByRole("region", { name: /trade history/i });
  expect(within(section).getAllByRole("row").length).toBe(16); // header + one page of 15
  await userEvent.click(within(section).getByRole("button", { name: "Best first" }));
  const first = within(section).getAllByRole("row")[1];
  expect(first).toHaveTextContent(/\+\d+\.\d bps/);
  await userEvent.selectOptions(within(section).getByLabelText(/symbol/i), "AAPL");
  for (const row of within(section).getAllByRole("row").slice(1)) expect(row).toHaveTextContent("AAPL");
  await userEvent.click(within(section).getAllByRole("button", { expanded: false })[0]);
  expect(within(section).getByText(/Costs took/)).toBeInTheDocument();
});

test("the ledger lists every trial and can be searched", async () => {
  show();
  const section = await screen.findByRole("region", { name: /trial ledger/i });
  expect(section).toHaveTextContent("25 on record");
  await userEvent.type(within(section).getByLabelText(/search the ledger/i), "vwap");
  expect(within(section).getAllByRole("listitem")).toHaveLength(1);
  await userEvent.clear(within(section).getByLabelText(/search the ledger/i));
  await userEvent.type(within(section).getByLabelText(/search the ledger/i), "zzz-nothing");
  expect(within(section).getByText("Nothing matches.")).toBeInTheDocument();
});

test("positions and runs explain their emptiness", async () => {
  show();
  expect(await screen.findByText(/Nothing is open/)).toBeInTheDocument();
  expect(screen.getByText(/No runs yet/)).toBeInTheDocument();
});

test("a lab that has not published yet is an empty state, not an error", async () => {
  show(new Error("Could not load lab.json (HTTP 404)"));
  expect(await screen.findByText(/has not tried anything yet/i)).toBeInTheDocument();
  expect(screen.queryByRole("alert")).toBeNull();
});

test("any other failure is shown as an error with a retry", async () => {
  show(new Error("Could not load lab.json (HTTP 500)"));
  expect(await screen.findByRole("alert")).toHaveTextContent(/500/);
});

test("a strategy with no trades does not crash the charts", async () => {
  const f = labFixture();
  show({ ...f, trades: [], strategies: f.strategies.map((s) => ({ ...s, equity_curve: [], backtest: {} })) });
  expect(await screen.findByText("Intraday Lab")).toBeInTheDocument();
  expect(screen.getByText(/no trades yet for this idea/i)).toBeInTheDocument();
});
