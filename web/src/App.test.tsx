import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";
import { UPDATED, row, strategies, stubFetch } from "./test-fixtures";

vi.mock("./components/ChartView", () => ({
  ChartView: ({ data, strategyId, candleStyle }: { data: { ticker: string }; strategyId: string; candleStyle: string }) => (
    <div data-testid="chart">{data.ticker}:{strategyId}:{candleStyle}</div>
  ),
}));

beforeEach(() => {
  window.location.hash = "#/";
  stubFetch();
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("home", () => {
  it("defaults to 1D and shows totals for the timeframe", async () => {
    render(<App />);
    await screen.findByText("What's moving today");
    expect(screen.getByRole("button", { name: "1D" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "4H" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByText("Daily")).toBeInTheDocument();
    const tiles = document.querySelectorAll(".stat .n");
    expect([...tiles].map((n) => n.textContent)).toEqual(["1", "1", "Daily"]);
  });

  it("switches to 4H, updates counts, and keeps the choice in the URL", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("What's moving today");
    await user.click(screen.getByRole("button", { name: "4H" }));
    expect(screen.getByText("4 hour")).toBeInTheDocument();
    expect([...document.querySelectorAll(".stat .n")].map((n) => n.textContent)).toEqual(["1", "0", "4 hour"]);
    expect(window.location.hash).toContain("tf=4h");
    await user.click(screen.getByRole("button", { name: "1D" }));
    expect(window.location.hash).not.toContain("tf=");
  });

  it("starts on 4H when the URL says so", async () => {
    window.location.hash = "#/?tf=4h";
    render(<App />);
    await screen.findByText("4 hour");
  });

  it("shows an error with a working retry when strategies fail to load", async () => {
    stubFetch(["strategies.json"]);
    const user = userEvent.setup();
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong");
    stubFetch();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    await screen.findByText("What's moving today");
  });

  it("warns when the data is stale", async () => {
    stubFetch([], { "strategies.json": { ...strategies, updated_at: "2020-01-01T00:00:00Z" } });
    render(<App />);
    expect(await screen.findByText(/looks out of date/)).toBeInTheDocument();
  });
});

describe("last updated", () => {
  it("is shown in the footer, not in the page header", async () => {
    stubFetch([], { "strategies.json": { ...strategies, updated_at: "2026-10-02T20:07:00+00:00" } });
    render(<App />);
    await screen.findByText("What's moving today");
    const footer = document.querySelector("footer")!;
    expect(footer).toHaveTextContent(/Last updated .*2026/);
    expect(footer).toHaveTextContent("Not financial advice");
    expect(document.querySelector(".hero")).not.toHaveTextContent(/Updated/);
  });
});

describe("market awareness", () => {
  const setNow = (iso: string) => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(iso));
  };

  it("shows the market as closed on a weekend with the next update time", async () => {
    setNow("2026-10-03T12:00:00Z");
    stubFetch([], { "strategies.json": { ...strategies, updated_at: "2026-10-02T20:07:00+00:00" } });
    render(<App />);
    const chip = await screen.findByTestId("market-status");
    expect(chip).toHaveTextContent("Market closed · Weekend · next update Mon 5 Oct, 13:35 ET");
    expect(screen.queryByText(/looks out of date/)).not.toBeInTheDocument(); // Friday's close is the latest update
  });

  it("shows the market as open with the next update today", async () => {
    setNow("2026-10-02T15:00:00Z");
    stubFetch([], { "strategies.json": { ...strategies, updated_at: "2026-10-02T13:40:00+00:00" } });
    render(<App />);
    expect(await screen.findByTestId("market-status")).toHaveTextContent("Market open · next update today 13:35 ET");
  });

  it("names the holiday", async () => {
    setNow("2026-11-26T15:00:00Z");
    stubFetch([], { "strategies.json": { ...strategies, updated_at: "2026-11-25T21:07:00+00:00" } });
    render(<App />);
    expect(await screen.findByTestId("market-status")).toHaveTextContent("Market closed · Thanksgiving");
  });

  it("warns when an update is more than 3 hours overdue", async () => {
    setNow("2026-10-05T21:00:00Z"); // Monday: the 13:35 ET update is 3h25m late
    stubFetch([], { "strategies.json": { ...strategies, updated_at: "2026-10-02T20:07:00+00:00" } });
    render(<App />);
    expect(await screen.findByText(/looks out of date/)).toBeInTheDocument();
  });

  it("still works (no chip) when market.json cannot be loaded", async () => {
    stubFetch(["market.json"]);
    render(<App />);
    await screen.findByText("What's moving today");
    expect(screen.queryByTestId("market-status")).not.toBeInTheDocument();
  });
});

describe("strategy page", () => {
  beforeEach(() => {
    window.location.hash = "#/strategy/macd-rsi-reversal";
  });

  it("lists stock cards and filters them", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("Exxon Mobil");
    expect(screen.getByText("NVIDIA")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "SELL" }));
    expect(screen.queryByText("Exxon Mobil")).not.toBeInTheDocument();
    expect(screen.getByText("NVIDIA")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "All" }));
    await user.type(screen.getByLabelText("Search ticker or name"), "zzz");
    expect(screen.getByText(/No signals match these filters/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(screen.getByText("Exxon Mobil")).toBeInTheDocument();
  });

  it("marks a low-conviction signal as weaker and leaves ordinary ones unlabelled", async () => {
    render(<App />);
    await screen.findByText("Exxon Mobil");
    const weak = screen.getByText("NVIDIA").closest(".scard")!;
    const normal = screen.getByText("Exxon Mobil").closest(".scard")!;
    expect(weak).toHaveClass("weak");
    expect(within(weak as HTMLElement).getByText("Weaker")).toBeInTheDocument();
    expect(weak.querySelector(".pill")).toHaveClass("faint");
    expect(normal).not.toHaveClass("weak");
    expect(within(normal as HTMLElement).queryByText("Weaker")).not.toBeInTheDocument();
    expect(normal.querySelector(".pill")).not.toHaveClass("faint");
  });

  it("explains in the card tooltip why a short is demoted", async () => {
    render(<App />);
    await screen.findByText("NVIDIA");
    expect(screen.getByText("NVIDIA").closest(".scard")).toHaveAttribute(
      "title",
      expect.stringContaining("did not beat holding cash"),
    );
  });

  it("badges a high-conviction signal as strong", async () => {
    stubFetch([], {
      "macd-rsi-reversal/1d.json": {
        updated_at: UPDATED,
        signals: [row({ ticker: "DVN", name: "Devon Energy", conviction: "high" })],
      },
    });
    render(<App />);
    const card = (await screen.findByText("Devon Energy")).closest(".scard")!;
    expect(within(card as HTMLElement).getByText("Strong")).toBeInTheDocument();
    expect(card).not.toHaveClass("weak");
  });

  it("follows the global timeframe selector", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("Exxon Mobil");
    await user.click(screen.getByRole("button", { name: "4H" }));
    await screen.findByText("American Airlines");
    expect(screen.queryByText("Exxon Mobil")).not.toBeInTheDocument();
  });

  it("drops a sector filter that does not exist on the other timeframe instead of showing an empty list", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("Exxon Mobil");
    await user.selectOptions(screen.getByLabelText("Sector"), "Energy"); // only exists on 1D
    await user.click(screen.getByRole("button", { name: "4H" }));
    await screen.findByText("American Airlines"); // Industrials, must not be hidden by the stale 'Energy' choice
    expect(screen.getByLabelText("Sector")).toHaveValue("All sectors");
  });

  it("shows an empty state when a strategy has no signals", async () => {
    window.location.hash = "#/strategy/trend-pullback";
    render(<App />);
    expect(await screen.findByText("No signals right now.")).toBeInTheDocument();
  });

  it("shows an error when the signal file fails to load", async () => {
    stubFetch(["macd-rsi-reversal/1d.json"]);
    render(<App />);
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });

  it("opens the chart modal on card click and closes with Escape", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: /XOM/ }));
    const dialog = await screen.findByRole("dialog", { name: "XOM chart" });
    await waitFor(() => expect(within(dialog).getByTestId("chart")).toHaveTextContent("XOM:macd-rsi-reversal:ha"));
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("defaults to Heikin-Ashi candles, switches to Real, and remembers the choice", async () => {
    const user = userEvent.setup();
    window.localStorage.removeItem("candleStyle");
    render(<App />);
    await user.click(await screen.findByRole("button", { name: /XOM/ }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByRole("button", { name: "Heikin-Ashi" })).toHaveAttribute("aria-pressed", "true");
    expect(within(dialog).getByRole("button", { name: "Real" })).toHaveAttribute("aria-pressed", "false");
    await within(dialog).findByText(/XOM:macd-rsi-reversal:ha/);
    await user.click(within(dialog).getByRole("button", { name: "Real" }));
    await within(dialog).findByText(/XOM:macd-rsi-reversal:real/);
    await user.keyboard("{Escape}");
    await user.click(screen.getByRole("button", { name: /XOM/ }));
    expect(within(await screen.findByRole("dialog")).getByRole("button", { name: "Real" })).toHaveAttribute("aria-pressed", "true");
    window.localStorage.removeItem("candleStyle");
  });

  it("shows an error inside the modal when the chart file is missing", async () => {
    stubFetch(["charts/1d/XOM.json"]);
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: /XOM/ }));
    expect(await within(await screen.findByRole("dialog")).findByRole("alert")).toBeInTheDocument();
  });

  it("shows 'unknown strategy' for a bad id", async () => {
    window.location.hash = "#/strategy/nope";
    render(<App />);
    expect(await screen.findByText(/Unknown strategy/)).toBeInTheDocument();
  });
});

describe("strategy change history", () => {
  beforeEach(() => {
    window.location.hash = "#/strategy/trend-pullback";
  });

  it("shows the current version next to the strategy name", async () => {
    render(<App />);
    await screen.findByRole("heading", { name: "Trend Pullback" });
    expect(screen.getByRole("button", { name: /change history for Trend Pullback/i })).toHaveTextContent("v1.2.0");
  });

  it("opens the history overlay on click, latest version first", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByRole("heading", { name: "Trend Pullback" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /change history/i }));
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveAccessibleName("Trend Pullback change history");
    const versions = within(dialog).getAllByRole("listitem").map((li) => li.querySelector(".ver")?.textContent);
    expect(versions).toEqual(["v1.2.0", "v1.1.0", "v1.0.0"]);
    expect(within(dialog).getByText(/none beat the current rules/)).toBeInTheDocument();
  });

  it("closes the overlay again", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByRole("heading", { name: "Trend Pullback" });
    await user.click(screen.getByRole("button", { name: /change history/i }));
    await user.click(screen.getByRole("button", { name: /close change history/i }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("shows each strategy its own history", async () => {
    const user = userEvent.setup();
    window.location.hash = "#/strategy/macd-rsi-reversal";
    render(<App />);
    await screen.findByRole("heading", { name: "MACD + RSI Reversal" });
    await user.click(screen.getByRole("button", { name: /change history/i }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getAllByRole("listitem")).toHaveLength(2);
    expect(within(dialog).getByText(/conviction tier/)).toBeInTheDocument();
  });
});

describe("strategy page with data written before versioning shipped", () => {
  it("renders without a history button instead of showing 'vundefined'", async () => {
    const legacy = {
      ...strategies,
      strategies: strategies.strategies.map(({ version, history, rules_version, ...rest }) => rest),
    };
    stubFetch([], { "strategies.json": legacy });
    window.location.hash = "#/strategy/trend-pullback";
    render(<App />);
    await screen.findByRole("heading", { name: "Trend Pullback" });
    expect(screen.queryByRole("button", { name: /change history/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/vundefined/)).not.toBeInTheDocument();
  });
});

describe("a signal whose setup has changed since it fired", () => {
  beforeEach(() => {
    window.location.hash = "#/strategy/macd-rsi-reversal";
  });

  it("is still listed, but carries a caveat badge", async () => {
    render(<App />);
    await screen.findByText("NVIDIA");
    const card = screen.getByText("NVIDIA").closest(".scard")!;
    const badge = within(card as HTMLElement).getByText("Setup changed");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveAttribute("title", expect.stringContaining("no longer holds"));
  });

  it("leaves a signal whose setup still holds unbadged", async () => {
    render(<App />);
    await screen.findByText("Exxon Mobil");
    const card = screen.getByText("Exxon Mobil").closest(".scard")!;
    expect(within(card as HTMLElement).queryByText("Setup changed")).not.toBeInTheDocument();
  });
});
