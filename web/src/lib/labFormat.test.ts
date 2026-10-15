import { expect, test } from "vitest";
import { NA, bps, hourLabel, pctPlain, ratio, signedPct, signedUsd, toneClass, usd } from "./labFormat";

test("signed figures carry their sign and zero is plain", () => {
  expect(bps(12.34)).toBe("+12.3 bps");
  expect(bps(-4.06)).toBe("-4.1 bps");
  expect(bps(0)).toBe("0.0 bps");
  expect(signedPct(1.234)).toBe("+1.23%");
  expect(signedUsd(1234)).toBe("+$1,234");
  expect(signedUsd(-50)).toBe("-$50");
});

test("a missing or non-finite figure is an em dash, never NaN or a blank", () => {
  for (const f of [bps, signedPct, pctPlain, ratio, usd, signedUsd]) {
    expect(f(null)).toBe(NA);
    expect(f(undefined)).toBe(NA);
    expect(f(Number.NaN)).toBe(NA);
  }
  expect(NA).not.toContain("--");
});

test("tone: gains green, losses red, zero and missing neutral", () => {
  expect(toneClass(1)).toBe("buy-text");
  expect(toneClass(-1)).toBe("sell-text");
  expect(toneClass(0)).toBe("");
  expect(toneClass(null)).toBe("");
});

test("hour labels are twelve-hour", () => {
  expect(hourLabel("9")).toBe("9a");
  expect(hourLabel("12")).toBe("12p");
  expect(hourLabel("15")).toBe("3p");
  expect(pctPlain(0.5)).toBe("50%");
});
