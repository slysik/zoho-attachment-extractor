from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


class TemplateRegistry:
    """Match incoming reports to extraction templates by subject/filename patterns."""

    def __init__(self, templates_path: Path | None = None) -> None:
        self.templates: list[dict[str, Any]] = []
        path = templates_path or Path(__file__).parent / "templates.yaml"
        if path.exists():
            with path.open() as f:
                data = yaml.safe_load(f)
                self.templates = data.get("templates", []) if data else []

    def match(self, subject: str = "", filename: str = "") -> dict[str, Any] | None:
        """Find the first matching template for a given email subject/filename."""
        text = f"{subject} {filename}".lower()
        for tpl in self.templates:
            pattern = tpl.get("match_pattern", "")
            if pattern and re.search(pattern, text, re.IGNORECASE):
                return tpl
        return None


registry = TemplateRegistry()
