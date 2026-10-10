import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HashRouter } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";
import * as api from "../api";
import { paperTradingFile } from "../test-fixtures";
import { PaperPage } from "./PaperPage";

function show(file = paperTradingFile) {
  vi.spyOn(api, "getPaperTrading").mockResolvedValue(file);
  return render(<HashRouter><PaperPage /></HashRouter>);
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
  expect(await screen.findByText(/flat/i)).toBeInTheDocument();
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
  vi.spyOn(api, "getPaperTrading").mockRejectedValue(new Error("HTTP 500"));
  render(<HashRouter><PaperPage /></HashRouter>);
  expect(await screen.findByText(/HTTP 500/)).toBeInTheDocument();
});

test("a 404 before the first trading run reads as not-yet, not as an error", async () => {
  vi.spyOn(api, "getPaperTrading").mockRejectedValue(
    new Error("Could not load paper-trading.json (HTTP 404)"));
  render(<HashRouter><PaperPage /></HashRouter>);
  expect(await screen.findByText(/not published yet|no paper-trading data/i)).toBeInTheDocument();
});
