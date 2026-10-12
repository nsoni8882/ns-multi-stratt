import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, test, vi } from "vitest";
import * as api from "../api";
import { strategies } from "../test-fixtures";
import { StrategiesProvider } from "../strategiesContext";
import { TopBar } from "./TopBar";

function at(path: string) {
  vi.spyOn(api, "getStrategies").mockResolvedValue(strategies);
  vi.spyOn(api, "getMarket").mockRejectedValue(new Error("not needed"));
  vi.spyOn(api, "getHealth").mockRejectedValue(new Error("not needed"));
  return render(
    <MemoryRouter initialEntries={[path]}>
      <StrategiesProvider><TopBar /></StrategiesProvider>
    </MemoryRouter>,
  );
}

test("the RSI(2) Reversion tab is always offered, even before strategies load", async () => {
  at("/");
  expect(await screen.findByRole("link", { name: "RSI(2) Reversion" })).toBeInTheDocument();
});

test("the timeframe toggle is offered on the signal lists", async () => {
  at("/");
  expect(await screen.findByRole("button", { name: /1D/i })).toBeInTheDocument();
});

test("the timeframe toggle is hidden on RSI(2) Reversion, which is daily only", async () => {
  at("/paper");
  await screen.findByRole("link", { name: "RSI(2) Reversion" });
  expect(screen.queryByRole("button", { name: /4H/i })).not.toBeInTheDocument();
});

test("the nav keeps its own grid column, so dropping the toggle cannot move it", async () => {
  at("/paper");
  // Why this is pinned: the bar was a flex row with space-between, and losing the third
  // child slid the nav from the middle to the right edge. The fix is structural — fixed
  // grid columns — so the nav must never be the element the end-alignment rule targets.
  const nav = await screen.findByRole("navigation", { name: "Primary" });
  expect(nav).toHaveClass("pillnav");
  expect(nav.parentElement).toHaveClass("top");
});
