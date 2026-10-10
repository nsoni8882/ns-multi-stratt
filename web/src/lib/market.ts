import type { MarketFile, MarketSession } from "../types";
import { isStale } from "./filters";

const ET = "America/New_York";
const MINUTE = 60_000;
const HOUR = 3_600_000;
const UPDATE_DELAY = 5 * MINUTE; // matches scanner/market.py
const FIRST_BAR = 4 * HOUR;
export const STALE_GRACE_HOURS = 3;

/** When the scanner should have refreshed the data: 5 minutes after each 4H/daily bar closes. */
export function updateDueTimes(s: MarketSession): Date[] {
  const open = Date.parse(s.open);
  const close = Date.parse(s.close);
  const firstBarClose = Math.min(open + FIRST_BAR, close); // early-close days have a single bar
  return [...new Set([firstBarClose, close])].sort((a, b) => a - b).map((t) => new Date(t + UPDATE_DELAY));
}

const allDue = (m: MarketFile): Date[] => m.sessions.flatMap(updateDueTimes).sort((a, b) => a.getTime() - b.getTime());

const etDate = (d: Date) => new Intl.DateTimeFormat("en-CA", { timeZone: ET }).format(d); // YYYY-MM-DD
const etWeekday = (d: Date) => new Intl.DateTimeFormat("en-US", { timeZone: ET, weekday: "short" }).format(d);

export interface MarketStatus {
  open: boolean;
  reason: string | null; // why it is closed (or "Early close today" while open)
  earlyClose: boolean;
  nextUpdate: Date | null;
}

export function marketStatus(m: MarketFile, now: Date): MarketStatus {
  const nextUpdate = allDue(m).find((t) => t > now) ?? null;
  const today = etDate(now);
  const session = m.sessions.find((s) => s.date === today);
  if (session) {
    const open = Date.parse(session.open);
    const close = Date.parse(session.close);
    if (now.getTime() >= open && now.getTime() < close) {
      return { open: true, reason: null, earlyClose: session.early, nextUpdate };
    }
    return { open: false, reason: now.getTime() < open ? "Pre-market" : "After hours", earlyClose: session.early, nextUpdate };
  }
  const weekday = etWeekday(now);
  const reason =
    weekday === "Sat" || weekday === "Sun" ? "Weekend" : (m.holidays.find((h) => h.date === today)?.name ?? "Market holiday");
  return { open: false, reason, earlyClose: false, nextUpdate };
}

/**
 * Stale = an update came due more than STALE_GRACE_HOURS ago and the data predates it.
 * Weekends, holidays and early closes never come due, so they cannot trigger it. Without a
 * calendar (market.json failed to load) fall back to counting weekday hours only.
 */
export function isDataStale(updatedAt: string, now: Date, market?: MarketFile): boolean {
  if (market) {
    const cutoff = now.getTime() - STALE_GRACE_HOURS * HOUR;
    const overdue = allDue(market).filter((t) => t.getTime() <= cutoff);
    if (overdue.length > 0) return Date.parse(updatedAt) < overdue[overdue.length - 1].getTime();
  }
  return isStale(updatedAt, now);
}

/** "today 16:05 ET" or "Mon 5 Oct, 13:35 ET". */
export function formatNextUpdate(next: Date, now: Date): string {
  const time = new Intl.DateTimeFormat("en-GB", { timeZone: ET, hour: "2-digit", minute: "2-digit", hour12: false }).format(next);
  if (etDate(next) === etDate(now)) return `today ${time} ET`;
  const day = new Intl.DateTimeFormat("en-GB", { timeZone: ET, weekday: "short", day: "numeric", month: "short" }).format(next);
  return `${day.replace(",", "")}, ${time} ET`;
}

/** The last date the paper-trading bot should have run, or null if it is up to date.
 *
 *  The bot runs once per session, so a session that has closed with no run since means it
 *  missed one — a workflow failure, a disabled schedule, an expired token. Without this the
 *  page shows a week-old account as though it were current, which is the one thing a
 *  portfolio panel must never do.
 */
export function missedRunSince(lastRunDate: string | undefined, m: MarketFile | undefined,
                               now: Date): string | null {
  if (!lastRunDate || !m) return null;
  const closed = m.sessions
    .filter((s) => new Date(s.close) < now && s.date > lastRunDate)
    .map((s) => s.date)
    .sort();
  return closed.length > 0 ? lastRunDate : null;
}
