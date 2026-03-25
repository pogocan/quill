"""InterviewEngine — pure logic, no LLM, no I/O."""

from dataclasses import dataclass
from typing import Any

from quill.session import Session


@dataclass
class Action:
    type: str  # "ask" | "auto_resolve" | "complete"
    field_key: str | None = None
    question: str | None = None
    agent_note: str | None = None
    source: str | None = None


class InterviewEngine:
    def __init__(self, questions: list[dict]):
        self.questions = questions

    def next_action(self, session: Session) -> Action:
        for q in self.questions:
            if q["key"] in session.fields:
                continue
            if not q.get("required", True):
                continue
            if not self.dependencies_met(q, session):
                continue
            source = q.get("source", "user")
            if source in ("rag", "inferred"):
                return Action(
                    type="auto_resolve",
                    field_key=q["key"],
                    question=q["question"],
                    agent_note=q.get("agent_note"),
                    source=source,
                )
            return Action(
                type="ask",
                field_key=q["key"],
                question=q["question"],
                agent_note=q.get("agent_note"),
                source="user",
            )
        return Action(type="complete")

    def is_complete(self, session: Session) -> bool:
        return len(self.missing_required(session)) == 0

    def missing_required(self, session: Session) -> list[str]:
        return [
            q["key"]
            for q in self.questions
            if q.get("required", True) and q["key"] not in session.fields
        ]

    def dependencies_met(self, field: dict, session: Session) -> bool:
        for dep in field.get("depends_on", []):
            if dep not in session.fields:
                return False
        return True
