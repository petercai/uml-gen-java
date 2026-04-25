#!/usr/bin/env python3
"""Utility for injecting a clickable config-file legend block into PlantUML content."""

from __future__ import annotations

from pathlib import Path


_ANCHOR = "\u2693"  # ⚓


def build_legend_lines(config_path: Path, workspace: Path) -> list[str]:
    """Return PlantUML legend lines for the given config file.

    Args:
        config_path: Absolute path to the YAML config file.
        workspace:   Absolute workspace root used to compute the relative path.

    Returns:
        Three-line list: ['legend top center', '  [[…]]', 'end legend'].
    """
    try:
        rel_config = config_path.relative_to(workspace).as_posix()
    except ValueError:
        rel_config = config_path.as_posix()

    return [
        "legend top center",
        f"  [[{rel_config}:1 {_ANCHOR}{rel_config}]]",
        "end legend",
    ]


def _find_existing_legend(lines: list[str]) -> tuple[int, int] | None:
    """Return (start_index, end_exclusive_index) of an existing legend block, or None."""
    for i, line in enumerate(lines):
        if line.strip().startswith("legend"):
            for j in range(i + 1, len(lines)):
                if lines[j].strip() == "end legend":
                    return (i, j + 1)
    return None


def _find_post_header_insert_point(lines: list[str]) -> int | None:
    """Return the line index where the legend should be inserted.

    The insertion point is immediately after all leading comment lines ('...')
    that follow the @startuml directive.
    """
    for i, line in enumerate(lines):
        if line.strip().startswith("@startuml"):
            j = i + 1
            while j < len(lines) and lines[j].strip().startswith("'"):
                j += 1
            return j
    return None


def insert_legend_block(puml_content: str, config_path: Path, workspace: Path) -> str:
    """Insert or update a clickable legend block in PlantUML content.

    The legend is placed immediately after the marketing header comment block
    (lines starting with ``'``) that follows the ``@startuml`` directive.  If a
    legend block already exists anywhere in the content it is replaced in-place
    so the operation is idempotent.

    Args:
        puml_content: Full PlantUML file content as a string.
        config_path:  Absolute path to the YAML config file to link.
        workspace:    Absolute workspace root for computing a relative link path.

    Returns:
        Updated PlantUML content with the legend block inserted/updated.
    """
    new_legend = build_legend_lines(config_path, workspace)
    lines = puml_content.split("\n")

    existing = _find_existing_legend(lines)
    if existing is not None:
        start, end = existing
        lines = lines[:start] + new_legend + lines[end:]
    else:
        insert_at = _find_post_header_insert_point(lines)
        if insert_at is None:
            return puml_content
        lines = lines[:insert_at] + new_legend + lines[insert_at:]

    return "\n".join(lines)
