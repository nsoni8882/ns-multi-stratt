import { NavLink, useLocation } from "react-router-dom";
import { useStrategies } from "../strategiesContext";
import { TimeframeToggle } from "./TimeframeToggle";

export function TopBar() {
  const { data } = useStrategies();
  const { search } = useLocation(); // keep ?tf= when navigating
  return (
    <header className="top">
      <NavLink to={{ pathname: "/", search }} className="brand">Multi Strategy</NavLink>
      <nav aria-label="Primary" className="pillnav">
        <NavLink to={{ pathname: "/", search }} end>Home</NavLink>
        {data?.strategies.map((s) => (
          <NavLink key={s.id} to={{ pathname: `/strategy/${s.id}`, search }}>{s.name}</NavLink>
        ))}
      </nav>
      <TimeframeToggle />
    </header>
  );
}
