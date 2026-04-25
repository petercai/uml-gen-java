#!/usr/bin/env python3
"""Shared intermediate representation models for umlgen frontends."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceRef:
    """Stable source location reference."""

    relpath: str
    line: int


@dataclass(frozen=True)
class MethodCallIR:
    """Call-site level IR for sequence generation."""

    method_name: str
    qualifier: str | None
    source: SourceRef


@dataclass(frozen=True)
class FieldIR:
    """Field/member IR."""

    name: str
    visibility: str
    source: SourceRef


@dataclass(frozen=True)
class MethodIR:
    """Method/constructor IR."""

    name: str
    visibility: str
    source: SourceRef
    return_type_names: tuple[str, ...] = ()
    parameter_type_names: tuple[str, ...] = ()
    calls: tuple[MethodCallIR, ...] = ()


@dataclass(frozen=True)
class TypeIR:
    """Type-level IR shared by class and sequence frontends."""

    language: str
    kind: str
    name: str
    package: str
    fqcn: str
    source: SourceRef
    extends_types: tuple[str, ...] = ()
    implements_types: tuple[str, ...] = ()
    dependency_types: tuple[str, ...] = ()
    fields: tuple[FieldIR, ...] = ()
    methods: tuple[MethodIR, ...] = ()


@dataclass(frozen=True)
class SourceIndexIR:
    """Workspace-scoped IR index returned by language frontends."""

    language: str
    types: tuple[TypeIR, ...] = ()
