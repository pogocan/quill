"""Artifact renderer — Jinja2 templates + session data."""

from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader

from quill.session import Session


class ArtifactRenderer:
    def __init__(self, templates_dir: str):
        self.templates_dir = Path(templates_dir)
        self.env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            keep_trailing_newline=True,
        )

    def render(
        self,
        template_name: str,
        session: Session,
        extra: dict | None = None,
    ) -> str:
        template = self.env.get_template(template_name)
        context = {**session.fields, "session": session}
        if extra:
            context.update(extra)
        return template.render(context)

    def render_all(self, session: Session) -> list[dict]:
        """Render all templates found in the templates directory."""
        results = []
        for path in sorted(self.templates_dir.glob("*.j2")):
            content = self.render(path.name, session)
            results.append(
                {
                    "name": path.stem,
                    "content": content,
                    "type": path.suffix.replace(".", ""),
                }
            )
        return results
