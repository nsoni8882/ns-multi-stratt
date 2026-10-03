import { createContext, useContext, type ReactNode } from "react";
import { getHealth, getMarket, getStrategies } from "./api";
import { useAsync, type AsyncState } from "./hooks";
import type { HealthFile, MarketFile, StrategiesFile } from "./types";

type Value = AsyncState<StrategiesFile> & { market?: MarketFile; health?: HealthFile };
const Ctx = createContext<Value | null>(null);

export function StrategiesProvider({ children }: { children: ReactNode }) {
  const strategies = useAsync(getStrategies, []);
  const market = useAsync(getMarket, []); // optional: the site works without the calendar
  const health = useAsync(getHealth, []); // optional too: absent in data published before it existed
  return <Ctx.Provider value={{ ...strategies, market: market.data, health: health.data }}>{children}</Ctx.Provider>;
}

export function useStrategies(): Value {
  const v = useContext(Ctx);
  if (!v) throw new Error("useStrategies must be used inside StrategiesProvider");
  return v;
}
