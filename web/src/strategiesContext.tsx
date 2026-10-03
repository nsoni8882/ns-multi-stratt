import { createContext, useContext, type ReactNode } from "react";
import { getMarket, getStrategies } from "./api";
import { useAsync, type AsyncState } from "./hooks";
import type { MarketFile, StrategiesFile } from "./types";

type Value = AsyncState<StrategiesFile> & { market?: MarketFile };
const Ctx = createContext<Value | null>(null);

export function StrategiesProvider({ children }: { children: ReactNode }) {
  const strategies = useAsync(getStrategies, []);
  const market = useAsync(getMarket, []); // optional: the site works without the calendar
  return <Ctx.Provider value={{ ...strategies, market: market.data }}>{children}</Ctx.Provider>;
}

export function useStrategies(): Value {
  const v = useContext(Ctx);
  if (!v) throw new Error("useStrategies must be used inside StrategiesProvider");
  return v;
}
