from __future__ import annotations

from pathlib import Path

from ingest.config import repo_root


def web_dist_directory(dist_path: str | None = None) -> Path:
    configured = dist_path or "src/web/dist"
    path = Path(configured)
    if path.is_absolute():
        return path
    return repo_root() / configured
