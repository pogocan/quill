"""Capability base class and fallback chain."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class CapabilityResult:
    value: Any
    source: str
    confident: bool
    raw: Any = None


class Capability(ABC):
    name: str = ""
    fallback: "Capability | None" = None

    @abstractmethod
    def query(self, question: str) -> CapabilityResult: ...

    @property
    def available(self) -> bool:
        return True

    def query_with_fallback(self, question: str) -> CapabilityResult:
        if self.available:
            try:
                return self.query(question)
            except Exception:
                pass
        if self.fallback:
            return self.fallback.query_with_fallback(question)
        return CapabilityResult(value=None, source="none", confident=False)


class RAGCapability(Capability):
    """Base for any RAG implementation.

    Domain folder provides a concrete subclass,
    e.g. SunderRAGCapability wrapping sunder.Agent.
    """

    pass


class GraphCapability(Capability):
    """Base for knowledge graph queries."""

    pass
