"""The fixed menu. A family is a pure, causal function of closed bars; adding one is an
ordinary code change with tests, never something an LLM does at run time."""
from lab.families import gap_fade, orb, rsi2_intraday, vwap_reversion

REGISTRY = {
    "orb": orb,
    "vwap_reversion": vwap_reversion,
    "rsi2_intraday": rsi2_intraday,
    "gap_fade": gap_fade,
}
