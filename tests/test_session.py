"""Tests for quill.session."""

import json
import tempfile

from quill.session import Session, SessionManager, UserProfile, UserProfileManager


def test_new_session_has_empty_fields():
    with tempfile.TemporaryDirectory() as d:
        sm = SessionManager(d)
        session = sm.new_session()
        assert session.fields == {}
        assert session.field_sources == {}
        assert session.artifacts == []
        assert session.gaps == []
        assert session.history == []


def test_set_field_stores_value_and_source():
    with tempfile.TemporaryDirectory() as d:
        sm = SessionManager(d)
        session = sm.new_session()
        sm.set_field(session, "name", "Alice", "user")
        assert session.fields["name"] == "Alice"
        assert session.field_sources["name"] == "user"


def test_add_artifact_appends():
    with tempfile.TemporaryDirectory() as d:
        sm = SessionManager(d)
        session = sm.new_session()
        sm.add_artifact(session, "report.txt", "content", "text")
        assert len(session.artifacts) == 1
        assert session.artifacts[0]["name"] == "report.txt"
        assert session.artifacts[0]["content"] == "content"


def test_session_roundtrips_through_json():
    with tempfile.TemporaryDirectory() as d:
        sm = SessionManager(d)
        session = sm.new_session()
        sm.set_field(session, "x", 42, "inferred")
        sm.add_artifact(session, "out.sql", "SELECT 1", "sql")
        sm.save_session(session)
        loaded = sm.load_session(session.session_id)
        assert loaded.fields == session.fields
        assert loaded.artifacts == session.artifacts
        assert loaded.session_id == session.session_id


def test_user_profile_roundtrips_through_json():
    with tempfile.TemporaryDirectory() as d:
        pm = UserProfileManager(d)
        profile = pm.load_or_create("user1")
        pm.set_environment(profile, "hub_lpar", "PROD")
        pm.set_preference(profile, "verbose", True)
        pm.save(profile)
        loaded = pm.load_or_create("user1")
        assert loaded.environment["hub_lpar"] == "PROD"
        assert loaded.preferences["verbose"] is True


def test_set_environment_persists():
    with tempfile.TemporaryDirectory() as d:
        pm = UserProfileManager(d)
        profile = pm.load_or_create("u1")
        pm.set_environment(profile, "schema", "my_schema")
        assert profile.environment["schema"] == "my_schema"


def test_add_turn_appends_to_history():
    with tempfile.TemporaryDirectory() as d:
        sm = SessionManager(d)
        session = sm.new_session()
        sm.add_turn(session, "user", "hello")
        sm.add_turn(session, "assistant", "hi there")
        assert len(session.history) == 2
        assert session.history[0]["role"] == "user"
        assert session.history[1]["content"] == "hi there"
