"""Conductor — LLM layer over InterviewEngine."""

from dataclasses import dataclass, field
from typing import Any

from quill.capability import Capability
from quill.interview.engine import InterviewEngine
from quill.llm import AgentConfig, LLMProvider
from quill.session import Session, SessionManager

SYSTEM_PROMPT = (
    "You are a structured interview assistant. "
    "Ask questions naturally, confirm answers before storing, "
    "and guide the user through the process."
)


@dataclass
class ConductorResponse:
    message: str
    field_updates: dict = field(default_factory=dict)
    needs_confirmation: bool = False
    proposed_value: Any | None = None
    proposed_field: str | None = None
    is_complete: bool = False
    artifacts: list[dict] | None = None


class Conductor:
    def __init__(
        self,
        engine: InterviewEngine,
        session_manager: SessionManager,
        capabilities: dict[str, Capability],
        llm_provider: LLMProvider,
        config: AgentConfig | None = None,
    ):
        self.engine = engine
        self.session_manager = session_manager
        self.capabilities = capabilities
        self.llm = llm_provider
        self.config = config or AgentConfig()

    def run_turn(
        self, session: Session, user_input: str | None = None
    ) -> ConductorResponse:
        if user_input:
            self.session_manager.add_turn(session, "user", user_input)

        action = self.engine.next_action(session)

        if action.type == "complete":
            return ConductorResponse(
                message="All required information has been gathered.",
                is_complete=True,
            )

        if action.type == "auto_resolve":
            cap = self.capabilities.get(action.source)
            if cap:
                result = cap.query_with_fallback(action.question or "")
                if result.value is not None:
                    return ConductorResponse(
                        message=(
                            f"I found a value for {action.field_key}: "
                            f"{result.value}. Can you confirm this is correct?"
                        ),
                        needs_confirmation=True,
                        proposed_value=result.value,
                        proposed_field=action.field_key,
                    )
            return ConductorResponse(
                message=(
                    f"I couldn't automatically determine {action.field_key}. "
                    f"{action.question}"
                ),
            )

        # action.type == "ask" — use LLM to phrase naturally
        messages = [
            {
                "role": "user",
                "content": f"Ask the user this question naturally: {action.question}",
            }
        ]
        try:
            message = self.llm.complete(
                messages,
                system=self.config.system_prompt or SYSTEM_PROMPT,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
            )
        except Exception:
            message = action.question or ""

        self.session_manager.add_turn(session, "assistant", message)
        return ConductorResponse(message=message)
