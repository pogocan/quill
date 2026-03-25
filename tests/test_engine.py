"""Tests for quill.interview.engine."""

from quill.interview.engine import InterviewEngine
from quill.session import Session


def _session(**fields) -> Session:
    return Session(session_id="test", fields=fields, field_sources={})


QUESTIONS = [
    {
        "key": "field_a",
        "label": "Field A",
        "question": "What is A?",
        "required": True,
        "source": "user",
        "depends_on": [],
    },
    {
        "key": "field_b",
        "label": "Field B",
        "question": "What is B?",
        "required": True,
        "source": "rag",
        "depends_on": ["field_a"],
    },
    {
        "key": "field_c",
        "label": "Field C",
        "question": "What is C?",
        "required": True,
        "source": "inferred",
        "depends_on": ["field_a", "field_b"],
    },
    {
        "key": "field_d",
        "label": "Field D",
        "question": "What is D?",
        "required": False,
        "source": "user",
        "depends_on": [],
    },
]


def test_next_action_returns_ask_for_first_unresolved():
    engine = InterviewEngine(QUESTIONS)
    action = engine.next_action(_session())
    assert action.type == "ask"
    assert action.field_key == "field_a"


def test_next_action_skips_unmet_dependencies():
    engine = InterviewEngine(QUESTIONS)
    # field_a not resolved, so field_b (depends on a) should be skipped
    # engine returns field_a first
    action = engine.next_action(_session())
    assert action.field_key == "field_a"


def test_next_action_returns_auto_resolve_for_rag():
    engine = InterviewEngine(QUESTIONS)
    action = engine.next_action(_session(field_a="val_a"))
    assert action.type == "auto_resolve"
    assert action.field_key == "field_b"
    assert action.source == "rag"


def test_next_action_returns_auto_resolve_for_inferred():
    engine = InterviewEngine(QUESTIONS)
    action = engine.next_action(_session(field_a="a", field_b="b"))
    assert action.type == "auto_resolve"
    assert action.field_key == "field_c"
    assert action.source == "inferred"


def test_next_action_returns_complete_when_all_required_resolved():
    engine = InterviewEngine(QUESTIONS)
    action = engine.next_action(_session(field_a="a", field_b="b", field_c="c"))
    assert action.type == "complete"


def test_is_complete_false_when_required_missing():
    engine = InterviewEngine(QUESTIONS)
    assert engine.is_complete(_session(field_a="a")) is False


def test_is_complete_true_when_all_required_resolved():
    engine = InterviewEngine(QUESTIONS)
    assert engine.is_complete(_session(field_a="a", field_b="b", field_c="c")) is True


def test_missing_required_returns_correct_list():
    engine = InterviewEngine(QUESTIONS)
    missing = engine.missing_required(_session(field_a="a"))
    assert "field_b" in missing
    assert "field_c" in missing
    assert "field_a" not in missing
    assert "field_d" not in missing  # optional


def test_dependencies_met_with_nested():
    engine = InterviewEngine(QUESTIONS)
    field_c = QUESTIONS[2]
    assert engine.dependencies_met(field_c, _session()) is False
    assert engine.dependencies_met(field_c, _session(field_a="a")) is False
    assert engine.dependencies_met(field_c, _session(field_a="a", field_b="b")) is True
