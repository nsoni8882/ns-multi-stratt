"""What a round trip costs. Charged on both sides, against the trader: you buy above the
price you saw and sell below it. The stress run multiplies this."""
from lab import config


def tier_for(rank: int) -> str:
    return "mega" if rank < config.MEGA_RANK else "large"


def net_return(entry_px: float, exit_px: float, tier: str, mult: float = 1.0) -> float:
    c = config.COST_BPS_PER_SIDE[tier] * mult * 1e-4
    return exit_px * (1 - c) / (entry_px * (1 + c)) - 1
