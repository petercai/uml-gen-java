#!/usr/bin/env python3
"""Rule matching helpers for umlgen include/exclude lists."""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path


REGEX_META_CHARS = set("^$+?[](){}|")


def looks_like_file_rule(rule: str) -> bool:
    normalized = rule.replace("\\", "/")
    if "/" in normalized or "*" in normalized:
        return True
    return normalized.endswith(".java")


def looks_like_regex_rule(rule: str) -> bool:
    # Explicit regex markers take precedence over file-path heuristics.
    # e.g. ".*Dto.*" should be treated as regex, not a glob with wildcards.
    if rule.startswith(".*") or rule.endswith(".*"):
        return True
    if looks_like_file_rule(rule):
        return False
    return any(ch in REGEX_META_CHARS for ch in rule)


def looks_like_fqcn(rule: str) -> bool:
    if "/" in rule or "\\" in rule or "*" in rule:
        return False
    if looks_like_regex_rule(rule):
        return False
    parts = rule.split(".")
    if len(parts) < 2:
        return False
    return all(part and re.match(r"^[A-Za-z_$][\\w$]*$", part) for part in parts)


def normalize_path(value: str) -> str:
    return value.replace("\\", "/")


def rule_matches_type(
    *,
    rule: str,
    fqcn: str,
    short_name: str,
    relpath: str,
    absolute_path: Path,
    workspace: Path,
) -> bool:
    text = rule.strip()
    if not text:
        return False

    # Regex check MUST come before file-rule check: patterns like ".*Dto.*" contain
    # "*" which would make looks_like_file_rule() return True, causing fnmatch to fail
    # and the regex branch to never be reached.
    if looks_like_regex_rule(text):
        regex = re.compile(text)
        return bool(regex.search(fqcn) or regex.search(short_name) or regex.search(relpath))

    if looks_like_file_rule(text):
        normalized_rule = normalize_path(text)
        rel = normalize_path(relpath)
        name = absolute_path.name
        if fnmatch.fnmatch(rel, normalized_rule):
            return True
        if fnmatch.fnmatch(name, normalized_rule):
            return True

        candidate = Path(text)
        if not candidate.is_absolute():
            candidate = (workspace / candidate).resolve()
        return candidate == absolute_path

    if looks_like_fqcn(text):
        return fqcn == text

    return short_name == text


def rule_matches_method(rule: str, fqcn: str, short_name: str, relpath: str, method_name: str) -> bool:
    text = rule.strip()
    if not text:
        return False

    if ":" in text:
        left, right = text.rsplit(":", 1)
        left = left.strip()
        right = right.strip()
        if not right:
            return False
        if right != method_name:
            return False
        return rule_matches_type(
            rule=left,
            fqcn=fqcn,
            short_name=short_name,
            relpath=relpath,
            absolute_path=Path(relpath),
            workspace=Path("."),
        )

    if looks_like_regex_rule(text):
        regex = re.compile(text)
        target = f"{fqcn}.{method_name}"
        return bool(regex.search(target) or regex.search(method_name) or regex.search(short_name))

    if looks_like_file_rule(text):
        return fnmatch.fnmatch(normalize_path(relpath), normalize_path(text))

    return short_name == text or fqcn == text or method_name == text
