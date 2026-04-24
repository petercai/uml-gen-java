#!/usr/bin/env python3
"""Minimal Java source index for sequence call-chain extraction."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from pathlib import Path

PACKAGE_RE = re.compile(r"^\s*package\s+([A-Za-z_$][\w$.]*)\s*;")
TYPE_RE = re.compile(
    r"^\s*(?:public|protected|private)?\s*(?:abstract\s+|final\s+)?"
    r"(class|interface|enum|record)\s+([A-Za-z_$][\w$]*)\b"
)
METHOD_RE = re.compile(
    r"^\s*(?:public|protected|private)?\s*(?:static\s+|final\s+|abstract\s+|synchronized\s+|default\s+)*"
    r"(?:[A-Za-z_$][\w$<>\[\],.?\s]+\s+)?([A-Za-z_$][\w$]*)\s*\(([^)]*)\)"
)
FIELD_RE = re.compile(
    r"^\s*(?:public|protected|private)?\s*(?:static\s+)?(?:final\s+)?"
    r"([A-Za-z_$][\w$<>\[\],.?]*)\s+([a-zA-Z_$][\w$]*)\s*(?:=|;|,)"
)
LOCAL_VAR_RE = re.compile(
    r"\b([A-Za-z_$][\w$<>\[\],.?]*)\s+([a-zA-Z_$][\w$]*)\s*(?:=|;|,)"
)
QUALIFIED_CALL_RE = re.compile(r"\b([A-Za-z_$][\w$]*)\s*\.\s*([A-Za-z_$][\w$]*)\s*\(([^)]*)\)")
SIMPLE_CALL_RE = re.compile(r"(?<!\.)\b([A-Za-z_$][\w$]*)\s*\(([^)]*)\)")

KEYWORDS = {
    "if",
    "for",
    "while",
    "switch",
    "catch",
    "return",
    "throw",
    "new",
    "super",
    "this",
    "try",
}


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


def _short_type(type_expr: str) -> str:
    text = re.sub(r"<[^<>]*>", "", type_expr or "").replace("[]", "").strip()
    if not text:
        return ""
    return text.split(".")[-1]


def _find_package(lines: list[str]) -> str:
    for line in lines:
        matched = PACKAGE_RE.match(line)
        if matched:
            return matched.group(1)
    return ""


def _normalize_declared_type_name(raw: str) -> str:
    text = re.sub(r"<[^<>]*>", "", (raw or "")).replace("[]", "").strip()
    if not text:
        return ""
    return text.split(".")[-1]


def _parse_declared_types(raw: str) -> tuple[str, ...]:
    if not raw:
        return ()
    values: list[str] = []
    for part in raw.split(","):
        name = _normalize_declared_type_name(part)
        if name and name not in values:
            values.append(name)
    return tuple(values)


def _extract_parent_types_from_signature(signature: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    text = re.sub(r"\s+", " ", signature)
    extends_types: tuple[str, ...] = ()
    implements_types: tuple[str, ...] = ()

    # interface Foo extends A, B {
    interface_match = re.search(r"\binterface\b\s+[A-Za-z_$][\w$]*\s+extends\s+([^\{]+)", text)
    if interface_match:
        extends_types = _parse_declared_types(interface_match.group(1))

    # class Foo extends A implements B, C {
    extends_match = re.search(r"\bclass\b\s+[A-Za-z_$][\w$]*\s+extends\s+([^\{\s]+(?:\s*<[^{}>]*>)?)", text)
    if extends_match:
        extends_types = _parse_declared_types(extends_match.group(1))

    implements_match = re.search(r"\b(?:class|record)\b\s+[A-Za-z_$][\w$]*(?:\s+extends\s+[^\{]+?)?\s+implements\s+([^\{]+)", text)
    if implements_match:
        implements_types = _parse_declared_types(implements_match.group(1))

    return extends_types, implements_types


def _type_block_end(lines: list[str], start_line_index: int) -> int:
    depth = 0
    opened = False
    for i in range(start_line_index, len(lines)):
        for ch in lines[i]:
            if ch == "{":
                depth += 1
                opened = True
            elif ch == "}" and opened:
                depth -= 1
        if opened and depth == 0:
            return i
    return len(lines) - 1


def _collect_fields(lines: list[str], start: int, end: int) -> dict[str, str]:
    depth = 0
    fields: dict[str, str] = {}

    for i in range(start, end + 1):
        line = lines[i]
        current_depth = depth
        if current_depth == 1:
            match = FIELD_RE.match(line.strip())
            if match:
                fields[match.group(2)] = _short_type(match.group(1))

        for ch in line:
            if ch == "{":
                depth += 1
            elif ch == "}" and depth > 0:
                depth -= 1

    return fields


def _parse_method_calls(
    *,
    lines: list[str],
    method_start: int,
    method_end: int,
    method_name: str,
    fields: dict[str, str],
) -> list[MethodCall]:
    calls: list[MethodCall] = []
    local_types: dict[str, str] = {}

    for i in range(method_start, method_end + 1):
        raw = lines[i]
        text = raw.strip()
        if text.startswith("//"):
            continue

        local_decl = LOCAL_VAR_RE.search(text)
        if local_decl:
            local_types[local_decl.group(2)] = _short_type(local_decl.group(1))

        for match in QUALIFIED_CALL_RE.finditer(text):
            qualifier = match.group(1)
            called = match.group(2)
            if called in KEYWORDS:
                continue
            if called == method_name:
                # recursive call is still useful
                pass

            resolved_qualifier = qualifier
            if qualifier in local_types:
                resolved_qualifier = local_types[qualifier]
            elif qualifier in fields:
                resolved_qualifier = fields[qualifier]

            calls.append(MethodCall(method_name=called, qualifier=resolved_qualifier, call_line=i + 1))

        for match in SIMPLE_CALL_RE.finditer(text):
            called = match.group(1)
            if called in KEYWORDS:
                continue
            if f".{called}(" in text:
                continue
            calls.append(MethodCall(method_name=called, qualifier=None, call_line=i + 1))

    return calls


def _parse_methods(
    *,
    lines: list[str],
    type_fqcn: str,
    type_short_name: str,
    relpath: str,
    start: int,
    end: int,
    fields: dict[str, str],
) -> list[MethodDef]:
    methods: list[MethodDef] = []
    depth = 0
    i = start

    while i <= end:
        line = lines[i]
        current_depth = depth
        text = line.strip()

        if current_depth == 1 and "(" in text and not text.startswith(("if ", "for ", "while ", "switch ", "catch ")):
            signature = text
            sig_end = i
            while ")" not in signature and sig_end + 1 <= end:
                sig_end += 1
                signature += " " + lines[sig_end].strip()

            method_match = METHOD_RE.match(signature)
            if method_match:
                method_name = method_match.group(1)
                body_start = sig_end
                while body_start <= end and "{" not in lines[body_start]:
                    body_start += 1
                if body_start <= end:
                    body_depth = 0
                    body_end = body_start
                    for j in range(body_start, end + 1):
                        for ch in lines[j]:
                            if ch == "{":
                                body_depth += 1
                            elif ch == "}" and body_depth > 0:
                                body_depth -= 1
                        if body_depth == 0 and j > body_start:
                            body_end = j
                            break

                    methods.append(
                        MethodDef(
                            type_fqcn=type_fqcn,
                            type_short_name=type_short_name,
                            relpath=relpath,
                            method_name=method_name,
                            decl_line=i + 1,
                            calls=_parse_method_calls(
                                lines=lines,
                                method_start=body_start,
                                method_end=body_end,
                                method_name=method_name,
                                fields=fields,
                            ),
                        )
                    )
                    i = body_end

        for ch in line:
            if ch == "{":
                depth += 1
            elif ch == "}" and depth > 0:
                depth -= 1

        i += 1

    return methods


def index_source_tree(workspace: Path, src_root: Path) -> SequenceIndex:
    java_files = sorted(p for p in src_root.rglob("*.java") if p.is_file())

    types_by_fqcn: dict[str, TypeDef] = {}
    methods_by_key: dict[tuple[str, str], MethodDef] = {}
    methods_by_short_type: dict[str, list[MethodDef]] = {}

    for java_file in java_files:
        lines = java_file.read_text(encoding="utf-8", errors="ignore").splitlines()
        package = _find_package(lines)
        relpath = java_file.relative_to(workspace).as_posix()

        for i, line in enumerate(lines):
            type_match = TYPE_RE.match(line)
            if not type_match:
                continue

            signature = line.strip()
            sig_end = i
            while "{" not in signature and sig_end + 1 < len(lines):
                sig_end += 1
                signature += " " + lines[sig_end].strip()
            extends_types, implements_types = _extract_parent_types_from_signature(signature)

            type_short_name = type_match.group(2)
            type_fqcn = f"{package}.{type_short_name}" if package else type_short_name
            type_end = _type_block_end(lines, i)
            types_by_fqcn[type_fqcn] = TypeDef(
                fqcn=type_fqcn,
                short_name=type_short_name,
                relpath=relpath,
                decl_line=i + 1,
                extends_types=extends_types,
                implements_types=implements_types,
            )

            fields = _collect_fields(lines, i, type_end)
            methods = _parse_methods(
                lines=lines,
                type_fqcn=type_fqcn,
                type_short_name=type_short_name,
                relpath=relpath,
                start=i,
                end=type_end,
                fields=fields,
            )
            for method in methods:
                methods_by_key[(method.type_fqcn, method.method_name)] = method
                methods_by_short_type.setdefault(method.type_short_name, []).append(method)

    return SequenceIndex(
        types_by_fqcn=types_by_fqcn,
        methods_by_key=methods_by_key,
        methods_by_short_type=methods_by_short_type,
    )
