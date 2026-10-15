"""A strategy is data: a family from the fixed registry, its parameters, and its risk rules.
Specs arrive from the owner or from the /lab skill; validation here is what stands between a
bad proposal and a crash (or a lookahead) mid-backtest."""
import hashlib
import json
import math
from dataclasses import asdict, dataclass

from lab import config
from lab.families import REGISTRY


class SpecError(ValueError):
    pass


RISK_BOUNDS = {"stop_pct": (0.0005, 0.10), "target_pct": (0.0005, 0.20),
               "max_hold_bars": (1, 78), "size_pct": (0.01, 0.25), "max_concurrent": (1, 20)}


def _number(name, value, lo, hi):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise SpecError(f"{name} must be a finite number, got {value!r}")
    if not lo <= value <= hi:
        raise SpecError(f"{name}={value} outside [{lo}, {hi}]")
    return value


@dataclass(frozen=True)
class Risk:
    stop_pct: float
    target_pct: float
    max_hold_bars: int
    size_pct: float = 0.10
    max_concurrent: int = 5

    def __post_init__(self):
        for k, (lo, hi) in RISK_BOUNDS.items():
            _number(f"risk.{k}", getattr(self, k), lo, hi)


@dataclass(frozen=True)
class Spec:
    name: str
    family: str
    timeframe: str
    params: dict
    risk: Risk
    hypothesis: str

    @classmethod
    def from_dict(cls, d: dict) -> "Spec":
        family = d.get("family")
        if family not in REGISTRY:
            raise SpecError(f"unknown family {family!r}; choose from {sorted(REGISTRY)}")
        if d.get("timeframe") not in config.TIMEFRAMES:
            raise SpecError(f"timeframe must be one of {config.TIMEFRAMES}")
        if not str(d.get("hypothesis", "")).strip():
            raise SpecError("a hypothesis is required, and must be written before testing")
        mod = REGISTRY[family]
        given = dict(d.get("params") or {})
        unknown = set(given) - set(mod.DEFAULTS)
        if unknown:
            raise SpecError(f"unknown params for {family}: {sorted(unknown)}")
        params = {**mod.DEFAULTS, **given}
        for k, (lo, hi) in mod.BOUNDS.items():
            _number(f"params.{k}", params[k], lo, hi)
        try:
            risk = Risk(**d["risk"])
        except (KeyError, TypeError) as e:
            raise SpecError(f"risk is invalid: {e}") from None
        return cls(str(d.get("name") or family), family, d["timeframe"], params, risk,
                   str(d["hypothesis"]).strip())

    def canonical(self) -> dict:
        """What changes behaviour: not the name, not the prose."""
        return {"family": self.family, "timeframe": self.timeframe,
                "params": dict(sorted(self.params.items())), "risk": asdict(self.risk)}

    def fingerprint(self) -> str:
        return hashlib.sha256(json.dumps(self.canonical(), sort_keys=True).encode()).hexdigest()[:12]

    def to_dict(self) -> dict:
        return {"name": self.name, "hypothesis": self.hypothesis, **self.canonical()}
