"""Config loader — reads config.yaml from the domain folder."""

from pathlib import Path

import yaml

from quill.llm import AgentConfig


def load_config(path: str = "config.yaml") -> dict:
    """Read config.yaml from the given path. Returns {} if not found."""
    p = Path(path)
    if not p.exists():
        return {}
    return yaml.safe_load(p.read_text()) or {}


def agent_config_from_file(path: str = "config.yaml") -> AgentConfig:
    """Build an AgentConfig from config.yaml.

    Resolution: config.yaml > env vars > AgentConfig defaults.
    """
    raw = load_config(path)
    llm = raw.get("llm", {})
    return AgentConfig(
        provider=llm.get("provider", AgentConfig.provider),
        model=llm.get("model"),
        ollama_base_url=llm.get("ollama_base_url", AgentConfig.ollama_base_url),
    )
