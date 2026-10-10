import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HashRouter } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";
import * as api from "../api";
import { StrategiesProvider } from "../strategiesContext";
import { chart, market, paperTradingFile, strategies } from "../test-fixtures";
import { PaperPage } from "./PaperPage";

/** PaperPage reads the trading calendar from the provider to spot a missed run, so the
 *  provider has to be present -- the same shape App renders it in. */
function page() {
  return (
    <HashRouter>
      <StrategiesProvider><PaperPage /></StrategiesProvider>
    </HashRouter>
  );
}

function show(file = paperTradingFile) {
  vi.spyOn(api, "getStrategies").mockResolvedValue(strategies);
  vi.spyOn(api, "getMarket").mockResolvedValue(market);
  vi.spyOn(api, "getHealth").mockRejectedValue(new Error("not needed"));
  vi.spyOn(api, "getPaperTrading").mockResolvedValue(file);
  return render(page());
}

beforeEach(() => {
  api.clearCache();
  vi.restoreAllMocks();
});

test("shows the opening balance and the total P/L", async () => {
  show();
  expect(await screen.findByText("$100,000")).toBeInTheDocument();
  // The fixture's total and unrealised P/L are both +$592, so more than one cell matches.
  expect(screen.getAllByText(/\+\$592/).length).toBeGreaterThan(0);
});

test("says the money is not real", async () => {
  show();
  expect(await screen.findByText("Paper money")).toBeInTheDocument();
});

test("renders a day-one account with no trades without crashing", async () => {
  show({
    ...paperTradingFile,
    account: { ...paperTradingFile.account, equity: 100000, total_pl: 0, total_pl_pct: 0,
               unrealised_pl: 0, deployed_pct: 0, cash: 100000 },
    positions: [], equity_curve: [], trades: [],
  });
  // "Flat" also appears as a pill on each chart tile, so scope to the positions panel.
  const positions = await screen.findByRole("region", { name: "Open positions" });
  expect(within(positions).getByText(/flat/i)).toBeInTheDocument();
});

test("offers no verdict before the acceptance bar is met", async () => {
  show();
  expect(await screen.findByText(/0 of 30/)).toBeInTheDocument();
  expect(screen.queryByText(/verdict:/i)).not.toBeInTheDocument();
});

test("warns when the last run landed past the cutoff", async () => {
  show({
    ...paperTradingFile,
    runs: [{ ...paperTradingFile.runs[0], late: true,
             skip_reason: "inside the 10-minute cutoff; cls orders would be rejected" }],
  });
  // The reason appears in the banner and again in the run log, and the loading spinner is a
  // status too, so address the banner by name.
  expect(await screen.findByRole("status", { name: "Last run warning" }))
    .toHaveTextContent(/cutoff/i);
});

test("the clock icon opens the change history", async () => {
  show();
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: /change history/i }));
  expect(screen.getByRole("dialog")).toHaveTextContent(/first version/i);
});

test("shows an error state with a retry when the file cannot be loaded", async () => {
  vi.spyOn(api, "getStrategies").mockResolvedValue(strategies);
  vi.spyOn(api, "getMarket").mockResolvedValue(market);
  vi.spyOn(api, "getHealth").mockRejectedValue(new Error("not needed"));
  vi.spyOn(api, "getPaperTrading").mockRejectedValue(new Error("HTTP 500"));
  render(page());
  expect(await screen.findByText(/HTTP 500/)).toBeInTheDocument();
});

test("a 404 before the first trading run reads as not-yet, not as an error", async () => {
  vi.spyOn(api, "getStrategies").mockResolvedValue(strategies);
  vi.spyOn(api, "getMarket").mockResolvedValue(market);
  vi.spyOn(api, "getHealth").mockRejectedValue(new Error("not needed"));
  vi.spyOn(api, "getChart").mockResolvedValue(chart);
  vi.spyOn(api, "getPaperTrading").mockRejectedValue(
    new Error("Could not load paper-trading.json (HTTP 404)"));
  render(page());
  expect(await screen.findByText(/has not traded yet/i)).toBeInTheDocument();
  // Not an error state: no alert, no retry button.
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

test("announces a missed run when a session has closed since the bot last ran", async () => {
  // The fixture calendar's last session closes 2026-10-06; the run is older than that.
  vi.setSystemTime(new Date("2026-10-07T21:00:00Z"));
  show({
    ...paperTradingFile,
    runs: [{ ...paperTradingFile.runs[0], at: "2026-10-05T19:25:00+00:00", date: "2026-10-05" }],
  });
  expect(await screen.findByRole("status", { name: "Missed runs" }))
    .toHaveTextContent(/has not run since 2026-10-05/i);
  vi.useRealTimers();
});

test("before the first run the charts are still offered, not a bare sentence", async () => {
  vi.spyOn(api, "getStrategies").mockResolvedValue(strategies);
  vi.spyOn(api, "getMarket").mockResolvedValue(market);
  vi.spyOn(api, "getHealth").mockRejectedValue(new Error("not needed"));
  vi.spyOn(api, "getChart").mockResolvedValue(chart);
  vi.spyOn(api, "getPaperTrading").mockRejectedValue(
    new Error("Could not load paper-trading.json (HTTP 404)"));
  render(page());
  expect(await screen.findByText(/has not traded yet/i)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /AMZN chart/i })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /AAPL chart/i })).toBeInTheDocument();
});
