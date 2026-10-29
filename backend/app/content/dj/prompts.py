from pathlib import Path


def load_prompt(name: str) -> str:
    """Read a prompt text file from the app/content/prompts folder."""
    path = Path(__file__).parent.parent / "prompts" / f"{name}.txt"
    return path.read_text(encoding="utf-8")
