import math
from statistics import NormalDist

import numpy as np

EULER_GAMMA = 0.5772156649015329


def t_stat(x: np.ndarray) -> float:
    if len(x) < 2:
        return 0.0
    sd = float(np.std(x, ddof=1))
    return 0.0 if sd == 0 else float(np.mean(x)) / (sd / math.sqrt(len(x)))


def deflated_threshold(n_trials: int, base: float) -> float:
    """Expected maximum of n independent null t statistics (Bailey & Lopez de Prado's
    approximation), floored at `base`. One trial needs only the base."""
    if n_trials < 2:
        return base
    inv = NormalDist().inv_cdf
    e_max = (1 - EULER_GAMMA) * inv(1 - 1 / n_trials) + EULER_GAMMA * inv(1 - 1 / (n_trials * math.e))
    return max(base, e_max)
