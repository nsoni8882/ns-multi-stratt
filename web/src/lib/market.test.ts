import type { MarketFile } from "../types";
import { market } from "../test-fixtures";
import { formatNextUpdate, isDataStale, marketStatus, updateDueTimes, missedRunSince } from "./market";

const at = (iso: string) => new Date(iso);
const iso = (d: Date | null) => d?.toISOString();

describe("updateDueTimes", () => {
  it("regular day: first 4H bar close and the closing bar, each plus 5 minutes", () => {
    expect(updateDueTimes(market.sessions[1]).map(iso)).toEqual(["2026-10-02T17:35:00.000Z", "2026-10-02T20:05:00.000Z"]);
  });
  it("early-close day: a single update at the close", () => {
    expect(updateDueTimes(market.sessions[5]).map(iso)).toEqual(["2026-11-27T18:05:00.000Z"]);
  });
});

describe("marketStatus", () => {
  it("open during the session, with the next update later today", () => {
    const s = marketStatus(market, at("2026-10-02T15:00:00Z"));
    expect(s).toMatchObject({ open: true, reason: null, earlyClose: false });
    expect(iso(s.nextUpdate)).toBe("2026-10-02T17:35:00.000Z");
  });
  it("pre-market and after hours", () => {
    expect(marketStatus(market, at("2026-10-02T11:00:00Z"))).toMatchObject({ open: false, reason: "Pre-market" });
    const after = marketStatus(market, at("2026-10-02T21:00:00Z"));
    expect(after).toMatchObject({ open: false, reason: "After hours" });
    expect(iso(after.nextUpdate)).toBe("2026-10-05T17:35:00.000Z");
  });
  it("weekend", () => {
    const s = marketStatus(market, at("2026-10-03T12:00:00Z"));
    expect(s).toMatchObject({ open: false, reason: "Weekend" });
    expect(iso(s.nextUpdate)).toBe("2026-10-05T17:35:00.000Z");
  });
  it("holiday, named, with the next update on the following (early-close) day", () => {
    const s = marketStatus(market, at("2026-11-26T15:00:00Z"));
    expect(s).toMatchObject({ open: false, reason: "Thanksgiving" });
    expect(iso(s.nextUpdate)).toBe("2026-11-27T18:05:00.000Z");
  });
  it("flags an early-close day while it is open", () => {
    expect(marketStatus(market, at("2026-11-27T16:00:00Z"))).toMatchObject({ open: true, earlyClose: true });
  });
  it("a weekday that is missing from the calendar is reported as a generic holiday", () => {
    expect(marketStatus(market, at("2026-10-07T15:00:00Z"))).toMatchObject({ open: false, reason: "Market holiday" });
  });
});

describe("isDataStale (calendar based)", () => {
  const friClose = "2026-10-02T20:07:00Z";
  it("is not stale over the weekend after Friday's close", () => {
    expect(isDataStale(friClose, at("2026-10-03T12:00:00Z"), market)).toBe(false);
    expect(isDataStale(friClose, at("2026-10-05T14:00:00Z"), market)).toBe(false); // Monday morning, nothing due yet
  });
  it("is not stale on a holiday", () => {
    expect(isDataStale("2026-11-25T21:07:00Z", at("2026-11-26T15:00:00Z"), market)).toBe(false);
  });
  it("is stale when the last bar of the week was missed", () => {
    expect(isDataStale("2026-10-02T17:36:00Z", at("2026-10-03T12:00:00Z"), market)).toBe(true);
  });
  it("allows a 3 hour grace period after an update comes due", () => {
    expect(isDataStale(friClose, at("2026-10-05T20:00:00Z"), market)).toBe(false); // Monday 17:35 due, 2h25m late
    expect(isDataStale(friClose, at("2026-10-05T21:00:00Z"), market)).toBe(true); // 3h25m late
  });
  it("falls back to a weekday-hours rule without a calendar", () => {
    expect(isDataStale("2026-10-02T20:05:00Z", at("2026-10-05T12:00:00Z"), undefined)).toBe(false);
    expect(isDataStale("2026-09-28T12:00:00Z", at("2026-09-30T20:00:00Z"), undefined)).toBe(true);
  });
});

describe("formatNextUpdate", () => {
  it("uses 'today' for the same Eastern date, otherwise the weekday and date", () => {
    expect(formatNextUpdate(at("2026-10-02T20:05:00Z"), at("2026-10-02T15:00:00Z"))).toBe("today 16:05 ET");
    expect(formatNextUpdate(at("2026-10-05T17:35:00Z"), at("2026-10-03T12:00:00Z"))).toBe("Mon 5 Oct, 13:35 ET");
  });
});

describe("missedRunSince", () => {
  const m: MarketFile = {
    updated_at: "2026-10-06T20:07:00+00:00",
    sessions: [
      { date: "2026-10-05", open: "2026-10-05T13:30:00+00:00", close: "2026-10-05T20:00:00+00:00", early: false },
      { date: "2026-10-06", open: "2026-10-06T13:30:00+00:00", close: "2026-10-06T20:00:00+00:00", early: false },
      { date: "2026-10-07", open: "2026-10-07T13:30:00+00:00", close: "2026-10-07T20:00:00+00:00", early: false },
    ],
    holidays: [],
  };

  it("says nothing when the bot ran on the last closed session", () => {
    expect(missedRunSince("2026-10-06", m, new Date("2026-10-06T21:00:00Z"))).toBeNull();
  });

  it("reports the last run when a later session has since closed", () => {
    expect(missedRunSince("2026-10-05", m, new Date("2026-10-07T21:00:00Z"))).toBe("2026-10-05");
  });

  it("does not complain mid-session, before the close", () => {
    expect(missedRunSince("2026-10-06", m, new Date("2026-10-07T15:00:00Z"))).toBeNull();
  });

  it("says nothing when the bot has never run or the calendar is missing", () => {
    expect(missedRunSince(undefined, m, new Date())).toBeNull();
    expect(missedRunSince("2026-10-05", undefined, new Date())).toBeNull();
  });
});
