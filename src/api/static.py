from __future__ import annotations

from pathlib import Path

from ingest.config import repo_root


def web_dist_directory(dist_path: str | None = None) -> Path:
    configured = dist_path or "src/web/dist"
    path = Path(configured)
    if path.is_absolute():
        return path
    cwd_path = Path.cwd() / configured
    if cwd_path.is_dir():
        return cwd_path
    return repo_root() / configured
