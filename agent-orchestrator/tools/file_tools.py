"""
File tools — read/write files in the Spring Boot project directory.
All paths are relative to SPRING_PROJECT_PATH defined in config.
"""
from __future__ import annotations

from pathlib import Path

import config


def write_project_file(relative_path: str, content: str) -> None:
    """
    Write `content` to `SPRING_PROJECT_PATH / relative_path`.
    Parent directories are created automatically.
    Raises on permission errors or disk-full.
    """
    full_path: Path = config.SPRING_PROJECT_PATH / relative_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(content, encoding="utf-8")


def read_project_file(relative_path: str) -> str:
    """
    Read and return the text content of `SPRING_PROJECT_PATH / relative_path`.
    Raises FileNotFoundError if the path does not exist.
    """
    full_path: Path = config.SPRING_PROJECT_PATH / relative_path
    return full_path.read_text(encoding="utf-8")


def list_project_files(sub_directory: str = "") -> list[str]:
    """
    Return all file paths (relative to project root) under `sub_directory`.
    Returns an empty list if the directory does not exist.
    """
    dir_path: Path = config.SPRING_PROJECT_PATH / sub_directory
    if not dir_path.exists():
        return []
    return [
        str(f.relative_to(config.SPRING_PROJECT_PATH)).replace("\\", "/")
        for f in dir_path.rglob("*")
        if f.is_file()
    ]
