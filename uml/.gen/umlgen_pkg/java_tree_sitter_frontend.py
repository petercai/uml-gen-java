#!/usr/bin/env python3
"""Java tree-sitter frontend adapter on top of umlgen IR."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from umlgen_pkg.ir_models import TypeIR
from umlgen_pkg.java_tree_sitter_ir import index_java_ir, parse_java_file_to_ir


@dataclass
class FieldInfo:
    name: str
    visibility: str
    line: int


@dataclass
class MethodInfo:
    name: str
    visibility: str
    line: int


@dataclass
class JavaTypeInfo:
    kind: str
    name: str
    package: str
    fqcn: str
    decl_line: int
    file_path: Path
    relpath: str
    extends_types: list[str] = field(default_factory=list)
    implements_types: list[str] = field(default_factory=list)
    dependency_types: list[str] = field(default_factory=list)
    fields: list[FieldInfo] = field(default_factory=list)
    methods: list[MethodInfo] = field(default_factory=list)


@dataclass
class MethodCall:
    method_name: str
    qualifier: str | None
    call_line: int


@dataclass
class MethodDef:
    type_fqcn: str
    type_short_name: str
    relpath: str
    method_name: str
    decl_line: int
    calls: list[MethodCall] = field(default_factory=list)


@dataclass
class TypeDef:
    fqcn: str
    short_name: str
    relpath: str
    decl_line: int
    extends_types: tuple[str, ...] = ()
    implements_types: tuple[str, ...] = ()


@dataclass
class SequenceIndex:
    types_by_fqcn: dict[str, TypeDef]
    methods_by_key: dict[tuple[str, str], MethodDef]
    methods_by_short_type: dict[str, list[MethodDef]]


def _type_ir_to_java_type_info(type_ir: TypeIR, workspace: Path) -> JavaTypeInfo:
    return JavaTypeInfo(
        kind=type_ir.kind,
        name=type_ir.name,
        package=type_ir.package,
        fqcn=type_ir.fqcn,
        decl_line=type_ir.source.line,
        file_path=(workspace / type_ir.source.relpath).resolve(),
        relpath=type_ir.source.relpath,
        extends_types=list(type_ir.extends_types),
        implements_types=list(type_ir.implements_types),
        dependency_types=list(type_ir.dependency_types),
        fields=[
            FieldInfo(name=field_ir.name, visibility=field_ir.visibility, line=field_ir.source.line)
            for field_ir in type_ir.fields
        ],
        methods=[
            MethodInfo(name=method_ir.name, visibility=method_ir.visibility, line=method_ir.source.line)
            for method_ir in type_ir.methods
        ],
    )


def _type_ir_to_type_def(type_ir: TypeIR) -> TypeDef:
    return TypeDef(
        fqcn=type_ir.fqcn,
        short_name=type_ir.name,
        relpath=type_ir.source.relpath,
        decl_line=type_ir.source.line,
        extends_types=type_ir.extends_types,
        implements_types=type_ir.implements_types,
    )


def _type_ir_to_method_defs(type_ir: TypeIR) -> list[MethodDef]:
    output: list[MethodDef] = []
    for method_ir in type_ir.methods:
        output.append(
            MethodDef(
                type_fqcn=type_ir.fqcn,
                type_short_name=type_ir.name,
                relpath=type_ir.source.relpath,
                method_name=method_ir.name,
                decl_line=method_ir.source.line,
                calls=[
                    MethodCall(
                        method_name=call_ir.method_name,
                        qualifier=call_ir.qualifier,
                        call_line=call_ir.source.line,
                    )
                    for call_ir in method_ir.calls
                ],
            )
        )
    return output


def parse_java_file(file_path: Path, workspace: Path) -> list[JavaTypeInfo]:
    return [_type_ir_to_java_type_info(type_ir, workspace) for type_ir in parse_java_file_to_ir(file_path, workspace)]


def index_workspace_types(workspace: Path, src_root: Path) -> tuple[dict[str, JavaTypeInfo], dict[str, list[JavaTypeInfo]]]:
    by_fqcn: dict[str, JavaTypeInfo] = {}
    by_simple: dict[str, list[JavaTypeInfo]] = {}

    index_ir = index_java_ir(workspace, src_root)
    for type_ir in index_ir.types:
        info = _type_ir_to_java_type_info(type_ir, workspace)
        by_fqcn[info.fqcn] = info
        by_simple.setdefault(info.name, []).append(info)

    return by_fqcn, by_simple


def index_source_tree(workspace: Path, src_root: Path) -> SequenceIndex:
    types_by_fqcn: dict[str, TypeDef] = {}
    methods_by_key: dict[tuple[str, str], MethodDef] = {}
    methods_by_short_type: dict[str, list[MethodDef]] = {}

    index_ir = index_java_ir(workspace, src_root)
    for type_ir in index_ir.types:
        types_by_fqcn[type_ir.fqcn] = _type_ir_to_type_def(type_ir)
        for method in _type_ir_to_method_defs(type_ir):
            methods_by_key[(method.type_fqcn, method.method_name)] = method
            methods_by_short_type.setdefault(method.type_short_name, []).append(method)

    return SequenceIndex(
        types_by_fqcn=types_by_fqcn,
        methods_by_key=methods_by_key,
        methods_by_short_type=methods_by_short_type,
    )
