import { NavLink, useLocation } from "react-router-dom";
import { useStrategies } from "../strategiesContext";
import { TimeframeToggle } from "./TimeframeToggle";

export function TopBar() {
  const { data } = useStrategies();
  const { search, hash, pathname } = useLocation(); // keep ?tf= when navigating
  // The paper strategy is daily only, so a 1D/4H switch there would promise something the
  // page cannot do. HashRouter puts the route in the hash; check both to be safe.
  const onPaper = pathname === "/paper" || hash.startsWith("#/paper");
  return (
    <header className="top">
      <NavLink to={{ pathname: "/", search }} className="brand">Multi Strategy</NavLink>
      <nav aria-label="Primary" className="pillnav">
        <NavLink to={{ pathname: "/", search }} end>Home</NavLink>
        {data?.strategies.map((s) => (
          <NavLink key={s.id} to={{ pathname: `/strategy/${s.id}`, search }}>{s.name}</NavLink>
        ))}
        {/* Not driven by strategies.json: this is a portfolio view, not a signal list. */}
        <NavLink to={{ pathname: "/paper", search }}>RSI(2) Reversion</NavLink>
      </nav>
      {!onPaper && <TimeframeToggle />}
    </header>
  );
}
