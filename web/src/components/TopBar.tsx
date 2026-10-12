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
      {/* Held in the layout rather than unmounted. `.top` is space-between with three
          children, so dropping this one slides the nav from the middle to the right edge the
          moment you open /paper. visibility:hidden keeps the exact slot — the labels are
          fixed, so it is pixel-identical — and takes the buttons out of both the tab order
          and the accessibility tree, which an unusable 1D/4H switch has no business being in. */}
      <div className={onPaper ? "slot-off" : undefined}>
        <TimeframeToggle />
      </div>
    </header>
  );
}
