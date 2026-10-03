import { createContext, useContext, type ReactNode } from "react";
import { getStrategies } from "./api";
import { useAsync, type AsyncState } from "./hooks";
import type { StrategiesFile } from "./types";

const Ctx = createContext<AsyncState<StrategiesFile> | null>(null);

export function StrategiesProvider({ children }: { children: ReactNode }) {
  const state = useAsync(getStrategies, []);
  return <Ctx.Provider value={state}>{children}</Ctx.Provider>;
}

export function useStrategies(): AsyncState<StrategiesFile> {
  const v = useContext(Ctx);
  if (!v) throw new Error("useStrategies must be used inside StrategiesProvider");
  return v;
}
