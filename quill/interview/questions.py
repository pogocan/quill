"""Load and validate questions.yaml."""

from pathlib import Path
from typing import Any

import yaml

REQUIRED_KEYS = {"key", "label", "question", "required", "source"}
VALID_SOURCES = {"user", "rag", "inferred"}


def load_questions(path: str | Path) -> list[dict]:
    """Load questions from a YAML file and validate them."""
    data = yaml.safe_load(Path(path).read_text())
    questions = data.get("questions", [])
    validate_questions(questions)
    return questions


def validate_questions(questions: list[dict]) -> None:
    """Validate question definitions."""
    keys_seen: set[str] = set()
    for q in questions:
        missing = REQUIRED_KEYS - set(q.keys())
        if missing:
            raise ValueError(f"Question '{q.get('key', '?')}' missing fields: {missing}")
        if q["source"] not in VALID_SOURCES:
            raise ValueError(
                f"Question '{q['key']}' has invalid source '{q['source']}'"
            )
        if q["key"] in keys_seen:
            raise ValueError(f"Duplicate question key: '{q['key']}'")
        keys_seen.add(q["key"])
        for dep in q.get("depends_on", []):
            if dep not in keys_seen:
                raise ValueError(
                    f"Question '{q['key']}' depends on '{dep}' "
                    f"which is not defined before it"
                )
