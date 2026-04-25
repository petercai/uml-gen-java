#!/usr/bin/env python3
"""Frontend registry for parser selection and reserved parser placeholders."""

from __future__ import annotations

from umlgen_pkg.frontends.base import FrontendSelection

try:
    from umlgen_pkg.java_tree_sitter_frontend import (
        index_source_tree as tree_sitter_sequence_indexer,
        index_workspace_types as tree_sitter_class_indexer,
    )
except ImportError:  # pragma: no cover - optional dependency at runtime
    tree_sitter_sequence_indexer = None
    tree_sitter_class_indexer = None


def _reserved_error(parser_name: str) -> ValueError:
    return ValueError(
        f"config.runtime.parser={parser_name} is reserved for a future bridge frontend and is not implemented yet"
    )


def resolve_java_frontend(parser_name: str) -> FrontendSelection:
    parser = (parser_name or "legacy").strip()

    if parser == "legacy":
        return FrontendSelection(
            class_indexer=None,
            sequence_indexer=None,
        )

    if parser == "tree-sitter":
        if tree_sitter_class_indexer is None or tree_sitter_sequence_indexer is None:
            raise ValueError("tree-sitter parser selected but dependencies are not installed")
        return FrontendSelection(
            class_indexer=tree_sitter_class_indexer,
            sequence_indexer=tree_sitter_sequence_indexer,
        )

    if parser in {"spoon", "ts-morph"}:
        raise _reserved_error(parser)

    raise ValueError(f"Unsupported parser: {parser}")
