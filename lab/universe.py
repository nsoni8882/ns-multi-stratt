"""A fixed liquid universe, point in time. Membership for year Y is ranked on year Y-1's mean
daily dollar volume, so no year's list knows anything from that year. Survivorship caveat:
candidate symbols come from today's S&P 500, so names that left the index are absent."""
import hashlib
import json

import pandas as pd

from lab import config, costs


def freeze(dollar_volume: pd.DataFrame, size: int = config.UNIVERSE_SIZE) -> "dict[int, list[str]]":
    by_year = dollar_volume.groupby(dollar_volume.index.year).mean()
    return {int(y) + 1: list(row.dropna().sort_values(ascending=False).head(size).index)
            for y, row in by_year.iterrows()}


def allowed_years(membership: "dict[int, list[str]]") -> "dict[str, set[int]]":
    out: "dict[str, set[int]]" = {}
    for year, symbols in membership.items():
        for s in symbols:
            out.setdefault(s, set()).add(year)
    return out


def tiers_from(membership: "dict[int, list[str]]") -> "dict[str, str]":
    latest = membership[max(membership)]
    tiers = {s: "large" for s in allowed_years(membership)}
    tiers.update({s: costs.tier_for(rank) for rank, s in enumerate(latest)})
    return tiers


def version(membership: "dict[int, list[str]]") -> str:
    blob = json.dumps({str(k): v for k, v in sorted(membership.items())}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:12]
