#!/usr/bin/env python3
"""Update yaml matched section without rewriting unrelated comments."""

from __future__ import annotations

from pathlib import Path


def _strip_existing_matched(lines: list[str]) -> list[str]:
    output: list[str] = []
    in_matched_block = False

    for line in lines:
        stripped = line.strip()

        if not in_matched_block and stripped.startswith("matched:") and not line.startswith(" "):
            in_matched_block = True
            continue

        if in_matched_block:
            if not stripped:
                continue
            if not line.startswith(" ") and ":" in stripped and not stripped.startswith("-"):
                in_matched_block = False
                output.append(line)
            continue

        output.append(line)

    return output


def write_matched_section(config_path: Path, matched: list[str]) -> None:
    existing = config_path.read_text(encoding="utf-8").splitlines()
    cleaned = _strip_existing_matched(existing)

    while cleaned and not cleaned[-1].strip():
        cleaned.pop()

    cleaned.append("matched:")
    if not matched:
        cleaned.append("  []")
    else:
        for item in matched:
            cleaned.append(f"  - {item}")

    config_path.write_text("\n".join(cleaned) + "\n", encoding="utf-8")
