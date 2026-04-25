#!/usr/bin/env python3
"""Plugin contracts for umlgen frontends."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class JavaClassIndexer(Protocol):
    """Contract for Java class-diagram source indexers."""

    def __call__(self, workspace: Path, src_root: Path) -> tuple[dict[str, Any], dict[str, list[Any]]]:
        """Return (by_fqcn, by_simple_name) indices."""


@runtime_checkable
class JavaSequenceIndexer(Protocol):
    """Contract for Java sequence-diagram source indexers."""

    def __call__(self, workspace: Path, src_root: Path) -> Any:
        """Return a sequence index object compatible with umls_gen consumers."""


@dataclass(frozen=True)
class FrontendSelection:
    """Selected frontend pair for class/sequence generation."""

    class_indexer: JavaClassIndexer | None
    sequence_indexer: JavaSequenceIndexer | None
