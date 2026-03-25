"""Demo: action sequence walkthrough + artifact rendering."""

import tempfile
from pathlib import Path

from quill.interview.engine import InterviewEngine
from quill.session import Session, SessionManager
from quill.artifacts.renderer import ArtifactRenderer

# ── 1. Action sequence for 4-field questions spec ──

QUESTIONS = [
    {"key": "field_a", "label": "Project Name", "question": "What is the project name?",
     "required": True, "source": "user", "depends_on": []},
    {"key": "field_b", "label": "Database Schema", "question": "What database schema is used?",
     "required": True, "source": "rag", "depends_on": ["field_a"]},
    {"key": "field_c", "label": "Connection String", "question": "What is the connection string?",
     "required": True, "source": "inferred", "depends_on": ["field_a", "field_b"]},
    {"key": "field_d", "label": "Notes", "question": "Any additional notes?",
     "required": False, "source": "user", "depends_on": []},
]

engine = InterviewEngine(QUESTIONS)
session = Session(session_id="demo", fields={}, field_sources={})

print("=" * 60)
print("ACTION SEQUENCE WALKTHROUGH")
print("=" * 60)

# Simulate resolving fields one by one
resolve_values = {
    "field_a": "my_project",
    "field_b": "public",
    "field_c": "postgresql://localhost/my_project",
}

step = 1
while True:
    action = engine.next_action(session)
    print(f"\nStep {step}: engine.next_action() ->")
    print(f"  type:      {action.type}")
    print(f"  field_key: {action.field_key}")
    print(f"  source:    {action.source}")
    print(f"  question:  {action.question}")

    if action.type == "complete":
        print("\n  All required fields resolved!")
        break

    # Simulate resolving the field
    key = action.field_key
    val = resolve_values.get(key, "demo_value")
    session.fields[key] = val
    session.field_sources[key] = action.source
    print(f"  -> Resolved {key} = {val!r}")
    step += 1

print(f"\nFinal session.fields: {session.fields}")
print(f"Missing required: {engine.missing_required(session)}")
print(f"Is complete: {engine.is_complete(session)}")

# ── 2. Artifact rendering ──

print("\n" + "=" * 60)
print("ARTIFACT RENDERING")
print("=" * 60)

with tempfile.TemporaryDirectory() as tmpdir:
    # Write a simple Jinja2 template
    tmpl = Path(tmpdir) / "report.txt.j2"
    tmpl.write_text(
        "Project Report\n"
        "==============\n"
        "Project: {{ field_a }}\n"
        "Schema:  {{ field_b }}\n"
        "Conn:    {{ field_c }}\n"
        "\n"
        "Session ID: {{ session.session_id }}\n"
        "Fields resolved: {{ session.fields | length }}\n"
    )

    renderer = ArtifactRenderer(tmpdir)
    output = renderer.render("report.txt.j2", session)

    print(f"\nTemplate: report.txt.j2")
    print(f"Rendered output:\n")
    print(output)
