"""Conductor — LLM layer over InterviewEngine."""

from dataclasses import dataclass, field
from typing import Any

from quill.capability import Capability
from quill.interview.engine import Action, InterviewEngine
from quill.llm import AgentConfig, LLMProvider
from quill.session import Session, SessionManager

SYSTEM_PROMPT = (
    "You are a structured interview assistant. "
    "Ask questions naturally, confirm answers before storing, "
    "and guide the user through the process. "
    "Do not greet the user on every turn. Only greet once at the start."
)

_CONFIRM_KEYWORDS = frozenset(
    {"yes", "y", "correct", "ok", "sure", "right", "yep", "yeah", "confirmed"}
)
_DENY_KEYWORDS = frozenset(
    {"no", "n", "wrong", "nope", "nah", "incorrect"}
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
        self.pending_field: str | None = None
        self._pending_question: str | None = None
        self._pending_agent_note: str | None = None
        self._pending_confirmation: dict | None = None  # {field, value, source}

    def run_turn(
        self, session: Session, user_input: str | None = None
    ) -> ConductorResponse:
        if user_input:
            self.session_manager.add_turn(session, "user", user_input)

        # --- Handle pending confirmation (user was asked to confirm a value) ---
        if user_input and self._pending_confirmation:
            return self._handle_confirmation(session, user_input)

        # --- Handle pending field (user was asked a question, this is their answer) ---
        if user_input and self.pending_field:
            return self._handle_field_answer(session, user_input)

        # --- No pending state — advance the interview ---
        return self._advance(session)

    def _advance(self, session: Session) -> ConductorResponse:
        """Get next action from engine and execute it."""
        action = self.engine.next_action(session)

        if action.type == "complete":
            self.pending_field = None
            self._pending_confirmation = None
            return ConductorResponse(
                message="All required information has been gathered.",
                is_complete=True,
            )

        if action.type == "auto_resolve":
            return self._handle_auto_resolve(session, action)

        # action.type == "ask"
        return self._handle_ask(session, action)

    def _handle_auto_resolve(
        self, session: Session, action: Action
    ) -> ConductorResponse:
        """Use capability to resolve a field, then ask user to confirm."""
        cap = self.capabilities.get(action.source)
        if cap:
            # Build a rich search query via LLM
            try:
                query = self.llm.complete(
                    [
                        {
                            "role": "user",
                            "content": (
                                f"You are building a search query for a document corpus.\n\n"
                                f"Field being resolved: {action.field_key}\n"
                                f"Base question: {action.question}\n"
                                f"Search hints: {action.agent_note}\n"
                                f"Known context: {session.fields}\n\n"
                                f"Write a specific, detailed search query that will "
                                f"find the most relevant information in the documents. "
                                f"Include specific terms from the context.\n"
                                f"Return only the search query, nothing else."
                            ),
                        }
                    ],
                    system="You write precise search queries for document retrieval. Return only the query.",
                    max_tokens=256,
                    temperature=0.0,
                ).strip()
            except Exception:
                # Fallback: manual query construction
                context = ", ".join(
                    f"{k}={v}" for k, v in session.fields.items()
                )
                query = action.question or ""
                if context:
                    query = f"{query} Context: {context}"
            result = cap.query_with_fallback(query)
            if result.value is not None:
                raw_value = result.value
                # Clean the RAG answer down to a short value
                try:
                    cleaned = self.llm.complete(
                        [
                            {
                                "role": "user",
                                "content": (
                                    f"The following is a RAG result for field "
                                    f"'{action.field_key}':\n{raw_value}\n\n"
                                    f"Extract just the core value as a short phrase "
                                    f"(2-5 words max). For example if the answer is "
                                    f"about cooking methods, return just \"steaming\" "
                                    f"or \"pan frying\".\n"
                                    f"Return only the extracted value, nothing else."
                                ),
                            }
                        ],
                        system="You extract short, clean values from verbose RAG results. Return only the value.",
                        max_tokens=64,
                        temperature=0.0,
                    ).strip()
                except Exception:
                    cleaned = str(raw_value)
                result.raw = raw_value
                self._pending_confirmation = {
                    "field": action.field_key,
                    "value": cleaned,
                    "source": action.source,
                }
                return ConductorResponse(
                    message=(
                        f"I found a value for {action.field_key}: "
                        f"{cleaned}. Can you confirm this is correct?"
                    ),
                    needs_confirmation=True,
                    proposed_value=cleaned,
                    proposed_field=action.field_key,
                )
        # Capability unavailable or returned nothing — fall back to asking
        return self._handle_ask(session, action)

    def _handle_ask(self, session: Session, action: Action) -> ConductorResponse:
        """Ask the user a question, using agent_note for LLM context."""
        system = self.config.system_prompt or SYSTEM_PROMPT
        if action.agent_note:
            system = f"{system}\n\nHint for this field: {action.agent_note}"

        messages = [
            {
                "role": "user",
                "content": f"Ask the user this question naturally: {action.question}",
            }
        ]
        try:
            message = self.llm.complete(
                messages,
                system=system,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
            )
        except Exception:
            message = action.question or ""

        self.pending_field = action.field_key
        self._pending_question = action.question
        self._pending_agent_note = action.agent_note
        self.session_manager.add_turn(session, "assistant", message)
        return ConductorResponse(message=message)

    def _handle_field_answer(
        self, session: Session, user_input: str
    ) -> ConductorResponse:
        """Extract a field value from the user's reply via LLM."""
        hint = f"\nHint: {self._pending_agent_note}" if self._pending_agent_note else ""
        prompt = (
            f"The user was asked: {self._pending_question}{hint}\n"
            f"User replied: {user_input}\n"
            f"Extract the field value as a single clean string. "
            f"If the answer is unclear or insufficient, return exactly: null"
        )
        try:
            extracted = self.llm.complete(
                [{"role": "user", "content": prompt}],
                system="You extract structured field values from conversational input. Return only the value, nothing else.",
                max_tokens=256,
                temperature=0.0,
            ).strip()
        except Exception:
            extracted = user_input.strip()

        if extracted.lower() == "null" or not extracted:
            # Unclear — ask again
            message = (
                f"I wasn't sure about your answer for {self.pending_field}. "
                f"Could you clarify? {self._pending_question}"
            )
            self.session_manager.add_turn(session, "assistant", message)
            return ConductorResponse(message=message)

        # Store the value
        field_key = self.pending_field
        self.session_manager.set_field(session, field_key, extracted, "user")
        self.pending_field = None
        self._pending_question = None
        self._pending_agent_note = None

        # Advance to next action
        return self._advance(session)

    def _handle_confirmation(
        self, session: Session, user_input: str
    ) -> ConductorResponse:
        """Handle yes/no confirmation of a proposed value."""
        conf = self._pending_confirmation
        self._pending_confirmation = None
        normalized = user_input.strip().lower().rstrip(".,!?")

        if normalized in _CONFIRM_KEYWORDS:
            self.session_manager.set_field(
                session, conf["field"], conf["value"], conf["source"]
            )
            return self._advance(session)

        if normalized in _DENY_KEYWORDS:
            # User rejected — ask them directly
            action = self.engine.next_action(session)
            if action.field_key == conf["field"]:
                return self._handle_ask(session, action)
            # Field already resolved or skipped somehow
            return self._advance(session)

        # Ambiguous — try LLM to classify
        try:
            result = self.llm.complete(
                [
                    {
                        "role": "user",
                        "content": (
                            f"The user was asked to confirm the value "
                            f"'{conf['value']}' for field '{conf['field']}'. "
                            f"They replied: '{user_input}'. "
                            f"Did they confirm? Reply exactly 'yes' or 'no'."
                        ),
                    }
                ],
                system="You classify user intent. Reply exactly 'yes' or 'no'.",
                max_tokens=8,
                temperature=0.0,
            ).strip().lower()
        except Exception:
            result = "no"

        if result == "yes":
            self.session_manager.set_field(
                session, conf["field"], conf["value"], conf["source"]
            )
            return self._advance(session)

        # Default to re-asking
        action = self.engine.next_action(session)
        if action.field_key == conf["field"]:
            return self._handle_ask(session, action)
        return self._advance(session)
