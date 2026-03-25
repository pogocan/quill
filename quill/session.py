"""Session and user profile management."""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class Session:
    session_id: str
    fields: dict = field(default_factory=dict)
    field_sources: dict = field(default_factory=dict)
    artifacts: list[dict] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "fields": self.fields,
            "field_sources": self.field_sources,
            "artifacts": self.artifacts,
            "gaps": self.gaps,
            "history": self.history,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        return cls(**data)


@dataclass
class UserProfile:
    user_id: str
    environment: dict = field(default_factory=dict)
    preferences: dict = field(default_factory=dict)
    history: list[dict] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "environment": self.environment,
            "preferences": self.preferences,
            "history": self.history,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "UserProfile":
        return cls(**data)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SessionManager:
    def __init__(self, session_dir: str):
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)

    def new_session(self) -> Session:
        now = _now()
        return Session(
            session_id=str(uuid.uuid4()),
            created_at=now,
            updated_at=now,
        )

    def load_session(self, session_id: str) -> Session:
        path = self.session_dir / f"{session_id}.json"
        data = json.loads(path.read_text())
        return Session.from_dict(data)

    def save_session(self, session: Session) -> None:
        session.updated_at = _now()
        path = self.session_dir / f"{session.session_id}.json"
        path.write_text(json.dumps(session.to_dict(), indent=2))

    def set_field(self, session: Session, key: str, value: Any, source: str) -> None:
        session.fields[key] = value
        session.field_sources[key] = source
        session.updated_at = _now()

    def add_artifact(
        self, session: Session, name: str, content: str, artifact_type: str
    ) -> None:
        session.artifacts.append(
            {"name": name, "content": content, "type": artifact_type}
        )
        session.updated_at = _now()

    def add_gap(self, session: Session, field: str) -> None:
        if field not in session.gaps:
            session.gaps.append(field)
        session.updated_at = _now()

    def add_turn(self, session: Session, role: str, content: str) -> None:
        session.history.append({"role": role, "content": content})
        session.updated_at = _now()


class UserProfileManager:
    def __init__(self, profile_dir: str):
        self.profile_dir = Path(profile_dir)
        self.profile_dir.mkdir(parents=True, exist_ok=True)

    def load_or_create(self, user_id: str) -> UserProfile:
        path = self.profile_dir / f"{user_id}.json"
        if path.exists():
            data = json.loads(path.read_text())
            return UserProfile.from_dict(data)
        now = _now()
        return UserProfile(user_id=user_id, created_at=now, updated_at=now)

    def save(self, profile: UserProfile) -> None:
        profile.updated_at = _now()
        path = self.profile_dir / f"{profile.user_id}.json"
        path.write_text(json.dumps(profile.to_dict(), indent=2))

    def set_environment(self, profile: UserProfile, key: str, value: Any) -> None:
        profile.environment[key] = value

    def set_preference(self, profile: UserProfile, key: str, value: Any) -> None:
        profile.preferences[key] = value

    def add_session_summary(
        self, profile: UserProfile, session_id: str, summary: str
    ) -> None:
        profile.history.append({"session_id": session_id, "summary": summary})
