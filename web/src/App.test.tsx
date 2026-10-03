import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";
import { strategies, stubFetch } from "./test-fixtures";

vi.mock("./components/ChartView", () => ({
  ChartView: ({ data, strategyId }: { data: { ticker: string }; strategyId: string }) => (
    <div data-testid="chart">{data.ticker}:{strategyId}</div>
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
    await waitFor(() => expect(within(dialog).getByTestId("chart")).toHaveTextContent("XOM:macd-rsi-reversal"));
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
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
