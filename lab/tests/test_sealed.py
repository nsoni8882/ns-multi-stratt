from pathlib import Path

LAB = Path(__file__).resolve().parents[1]


def test_only_the_gate_reads_trades_after_the_cutoff():
    """`.after(` is how a result is cut to the holdout. If anything but gate.py does it, the
    LLM-facing paths can see the sealed period."""
    offenders = [p.name for p in LAB.rglob("*.py")
                 if "tests" not in p.parts and p.name not in ("gate.py", "backtest.py")
                 and ".after(" in p.read_text()]
    assert offenders == []
