"""VerifierAgent — lightweight field and session verification."""

import json
from dataclasses import dataclass, field
from typing import Any

from quill.llm import LLMProvider
from quill.session import Session

FIELD_CHECK_SYSTEM = (
    "You are a verification agent. You check field values for "
    "plausibility and consistency. Respond with JSON only. "
    "Keys: ok (bool), warning (str|null), conflict (str|null), "
    "suggestion (str|null)."
)

SESSION_CHECK_SYSTEM = (
    "You verify session data for consistency. "
    "Respond with JSON only. "
    "Keys: ok (bool), issues (list[str]), warnings (list[str])."
)


@dataclass
class FieldCheckResult:
    ok: bool
    warning: str | None = None
    conflict: str | None = None
    suggestion: str | None = None


@dataclass
class SessionCheckResult:
    ok: bool
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


class VerifierAgent:
    def __init__(self, llm_provider: LLMProvider):
        self.llm = llm_provider

    def check_field(
        self,
        key: str,
        value: Any,
        session: Session,
        questions: list[dict],
    ) -> FieldCheckResult:
        """Single LLM call to verify a field value against session state."""
        existing = {k: v for k, v in session.fields.items() if k != key}
        prompt = (
            f"Field '{key}' is being set to: {value!r}\n"
            f"Existing fields: {existing}\n"
            f"Is this value plausible? Does it conflict with existing fields?"
        )
        try:
            text = self.llm.complete(
                [{"role": "user", "content": prompt}],
                system=FIELD_CHECK_SYSTEM,
                temperature=0.1,
            )
            data = json.loads(text)
            return FieldCheckResult(
                ok=data.get("ok", True),
                warning=data.get("warning"),
                conflict=data.get("conflict"),
                suggestion=data.get("suggestion"),
            )
        except Exception:
            return FieldCheckResult(ok=True)

    def check_session(
        self,
        session: Session,
        questions: list[dict],
    ) -> SessionCheckResult:
        """Single LLM call to verify full session consistency before rendering."""
        required_keys = [q["key"] for q in questions if q.get("required", True)]
        missing = [k for k in required_keys if k not in session.fields]
        if missing:
            return SessionCheckResult(ok=False, missing=missing)

        prompt = (
            f"All session fields: {session.fields}\n"
            f"Check for conflicts, implausible combinations, or inconsistencies."
        )
        try:
            text = self.llm.complete(
                [{"role": "user", "content": prompt}],
                system=SESSION_CHECK_SYSTEM,
                temperature=0.1,
            )
            data = json.loads(text)
            return SessionCheckResult(
                ok=data.get("ok", True),
                issues=data.get("issues", []),
                warnings=data.get("warnings", []),
            )
        except Exception:
            return SessionCheckResult(ok=True)
