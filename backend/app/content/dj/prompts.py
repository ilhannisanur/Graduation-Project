from pathlib import Path

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def load_prompt(name: str) -> str:
    """Read a prompt file and add the rules shared by every prompt."""
    path = PROMPTS_DIR / f"{name}.txt"
    own_rules = path.read_text(encoding="utf-8")
    common_rules = (PROMPTS_DIR / "common_rules.txt").read_text(encoding="utf-8")
    return f"{own_rules.rstrip()}\n\n{common_rules}"
