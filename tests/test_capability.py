"""Tests for quill.capability."""

from quill.capability import Capability, CapabilityResult


class WorkingCap(Capability):
    name = "working"

    def query(self, question: str) -> CapabilityResult:
        return CapabilityResult(value="found", source="working", confident=True)


class BrokenCap(Capability):
    name = "broken"

    def query(self, question: str) -> CapabilityResult:
        raise RuntimeError("boom")


class UnavailableCap(Capability):
    name = "unavailable"

    @property
    def available(self) -> bool:
        return False

    def query(self, question: str) -> CapabilityResult:
        raise RuntimeError("should not be called")


def test_query_with_fallback_uses_fallback_when_unavailable():
    fallback = WorkingCap()
    cap = UnavailableCap()
    cap.fallback = fallback
    result = cap.query_with_fallback("test")
    assert result.value == "found"
    assert result.source == "working"


def test_query_with_fallback_uses_fallback_when_query_raises():
    fallback = WorkingCap()
    cap = BrokenCap()
    cap.fallback = fallback
    result = cap.query_with_fallback("test")
    assert result.value == "found"
    assert result.source == "working"


def test_returns_none_when_no_fallback():
    cap = BrokenCap()
    result = cap.query_with_fallback("test")
    assert result.value is None
    assert result.source == "none"
    assert result.confident is False
