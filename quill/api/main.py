"""FastAPI backend with SSE streaming."""

import asyncio
import json
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from quill.session import Session, SessionManager

app = FastAPI(title="Quill", description="Document-grounded conversational assistant")

# These are set by the domain's startup code.
_session_manager: SessionManager | None = None
_conductor = None  # Conductor instance, set at startup


def configure(session_manager: SessionManager, conductor: Any) -> None:
    """Called by domain startup to wire in dependencies."""
    global _session_manager, _conductor
    _session_manager = session_manager
    _conductor = conductor


def _sm() -> SessionManager:
    if _session_manager is None:
        raise HTTPException(503, "Server not configured")
    return _session_manager


# -- Request models --

class TurnRequest(BaseModel):
    user_input: str | None = None
    field_updates: dict[str, Any] | None = None


# -- Endpoints --

@app.post("/session/new")
async def new_session():
    sm = _sm()
    session = sm.new_session()
    sm.save_session(session)
    return {"session_id": session.session_id}


@app.post("/session/{session_id}/turn")
async def run_turn(session_id: str, body: TurnRequest):
    sm = _sm()
    try:
        session = sm.load_session(session_id)
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")

    # Apply direct field updates from the UI
    if body.field_updates:
        for key, value in body.field_updates.items():
            sm.set_field(session, key, value, source="user_direct")

    if _conductor is None:
        raise HTTPException(503, "Conductor not configured")

    response = _conductor.run_turn(session, body.user_input)
    sm.save_session(session)
    return {
        "message": response.message,
        "field_updates": response.field_updates,
        "needs_confirmation": response.needs_confirmation,
        "proposed_value": response.proposed_value,
        "proposed_field": response.proposed_field,
        "is_complete": response.is_complete,
        "artifacts": response.artifacts,
    }


@app.get("/session/{session_id}/stream")
async def stream(session_id: str):
    sm = _sm()
    try:
        sm.load_session(session_id)
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")

    async def event_generator():
        yield f"data: {json.dumps({'type': 'connected', 'session_id': session_id})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/session/{session_id}/artifacts")
async def get_artifacts(session_id: str):
    sm = _sm()
    try:
        session = sm.load_session(session_id)
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")
    return {"artifacts": session.artifacts}


@app.get("/session/{session_id}")
async def get_session(session_id: str):
    sm = _sm()
    try:
        session = sm.load_session(session_id)
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")
    return session.to_dict()
