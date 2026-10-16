from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / ".claude" / "skills" / "lab" / "SKILL.md"


def test_the_skill_exists_and_is_named_lab():
    text = SKILL.read_text()
    assert text.startswith("---\nname: lab\n")
    assert "description:" in text.split("---")[1]


def test_it_forbids_touching_what_decides_a_verdict():
    """The skill is the LLM's operating manual; the protections have to be stated in it."""
    text = SKILL.read_text()
    for protected in ("lab/config.py", "lab/gate.py", "lab/costs.py", "lab/ACCEPTANCE.md",
                      "trials.jsonl", "registry.json", ".after("):
        assert protected in text, protected
    assert "Ask the user before running each backtest" in text
    assert "at most **three**" in text


def test_the_commands_it_tells_you_to_run_exist():
    text = SKILL.read_text()
    assert "python -m lab.review" in text and (ROOT / "lab" / "review.py").exists()
    assert "gh workflow run lab.yml" in text and (ROOT / ".github" / "workflows" / "lab.yml").exists()
    assert (ROOT / "lab" / "FINDINGS.md").exists()
