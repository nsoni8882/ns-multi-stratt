import { HashRouter, Route, Routes } from "react-router-dom";
import { StaleBanner } from "./components/Feedback";
import { MarketBar } from "./components/MarketBar";
import { TopBar } from "./components/TopBar";
import { isDataStale } from "./lib/market";
import { Home } from "./pages/Home";
import { StrategyPage } from "./pages/StrategyPage";
import { StrategiesProvider, useStrategies } from "./strategiesContext";

function Shell() {
  const { data, market } = useStrategies();
  return (
    <>
      <TopBar />
      {market && <MarketBar market={market} />}
      {data && isDataStale(data.updated_at, new Date(), market) && <StaleBanner />}
      <main>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/strategy/:id" element={<StrategyPage />} />
          <Route path="*" element={<p className="muted center">Page not found.</p>} />
        </Routes>
      </main>
      <footer className="foot">Not financial advice. Data from Yahoo Finance, may be delayed or inaccurate.</footer>
    </>
  );
}

export default function App() {
  return (
    <HashRouter>
      <StrategiesProvider>
        <Shell />
      </StrategiesProvider>
    </HashRouter>
  );
}
