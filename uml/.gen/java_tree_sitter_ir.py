#!/usr/bin/env python3
"""Java tree-sitter parser that emits umlgen IR models."""

from __future__ import annotations

from pathlib import Path

from ir_models import FieldIR, MethodCallIR, MethodIR, SourceIndexIR, SourceRef, TypeIR
from java_tree_sitter_support import (
    child_field_map,
    extract_type_names_from_node,
    iter_named_descendants,
    node_line,
    node_text,
    parse_java_tree,
    short_type_name,
    visibility_from_node,
)


TYPE_NODE_KINDS = {
    "class_declaration": "class",
    "interface_declaration": "interface",
    "enum_declaration": "enum",
    "record_declaration": "record",
}


def _dedupe_keep_order(items: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        output.append(item)
    return tuple(output)


def _top_level_type_nodes(root_node) -> list:
    return [child for child in root_node.named_children if child.type in TYPE_NODE_KINDS]


def _find_package_name(root_node, source: bytes) -> str:
    for child in root_node.named_children:
        if child.type == "package_declaration":
            text = node_text(source, child)
            if text.startswith("package "):
                return text[len("package "):].rstrip(" ;\n\t")
    return ""


def _declared_type_name(source: bytes, node) -> str:
    return node_text(source, child_field_map(node).get("name"))


def _extract_parent_types(source: bytes, node) -> tuple[tuple[str, ...], tuple[str, ...]]:
    extends_types: list[str] = []
    implements_types: list[str] = []

    for index, child in enumerate(node.children):
        field_name = node.field_name_for_child(index)
        if field_name == "superclass":
            extends_types.extend(extract_type_names_from_node(source, child))
            continue
        if field_name == "interfaces":
            implements_types.extend(extract_type_names_from_node(source, child))
            continue
        if child.type == "extends_interfaces":
            extends_types.extend(extract_type_names_from_node(source, child))

    return _dedupe_keep_order(extends_types), _dedupe_keep_order(implements_types)


def _field_declarator_names(source: bytes, node) -> list[str]:
    output: list[str] = []
    for child in node.named_children:
        if child.type != "variable_declarator":
            continue
        name_node = child_field_map(child).get("name")
        name = node_text(source, name_node)
        if name:
            output.append(name)
    return output


def _parameter_type_names(source: bytes, parameters_node) -> tuple[str, ...]:
    if parameters_node is None:
        return ()

    output: list[str] = []
    for child in parameters_node.named_children:
        if child.type not in {"formal_parameter", "spread_parameter", "receiver_parameter", "catch_formal_parameter"}:
            continue
        output.extend(extract_type_names_from_node(source, child_field_map(child).get("type")))
    return _dedupe_keep_order(output)


def _collect_field_types(source: bytes, body_node) -> dict[str, str]:
    output: dict[str, str] = {}
    if body_node is None:
        return output

    for child in body_node.named_children:
        if child.type != "field_declaration":
            continue
        type_names = extract_type_names_from_node(source, child_field_map(child).get("type"))
        short_name = short_type_name(type_names[0]) if type_names else ""
        if not short_name:
            continue
        for name in _field_declarator_names(source, child):
            output[name] = short_name
    return output


def _qualifier_text(source: bytes, object_node) -> str | None:
    if object_node is None:
        return None
    text = node_text(source, object_node).strip()
    if not text or text == "this":
        return None
    if text.startswith("this."):
        return text.split(".")[-1]
    return text.split(".")[-1]


def _collect_method_calls(source: bytes, body_node, field_types: dict[str, str], relpath: str) -> tuple[MethodCallIR, ...]:
    if body_node is None:
        return ()

    local_types: dict[str, str] = {}
    calls: list[MethodCallIR] = []

    for node in iter_named_descendants(body_node):
        if node.type == "local_variable_declaration":
            type_names = extract_type_names_from_node(source, child_field_map(node).get("type"))
            short_name = short_type_name(type_names[0]) if type_names else ""
            if not short_name:
                continue
            for name in _field_declarator_names(source, node):
                local_types[name] = short_name
            continue

        if node.type != "method_invocation":
            continue

        field_map = child_field_map(node)
        method_name = node_text(source, field_map.get("name"))
        qualifier = _qualifier_text(source, field_map.get("object"))
        if qualifier in local_types:
            qualifier = local_types[qualifier]
        elif qualifier in field_types:
            qualifier = field_types[qualifier]

        if method_name:
            calls.append(
                MethodCallIR(
                    method_name=method_name,
                    qualifier=qualifier,
                    source=SourceRef(relpath=relpath, line=node_line(node)),
                )
            )

    return tuple(calls)


def _collect_members(source: bytes, body_node, type_name: str, relpath: str, type_kind: str = "class") -> tuple[tuple[FieldIR, ...], tuple[MethodIR, ...], tuple[str, ...]]:
    fields: list[FieldIR] = []
    methods: list[MethodIR] = []
    dependencies: list[str] = []
    is_interface = type_kind == "interface"

    if body_node is None:
        return (), (), ()

    field_types = _collect_field_types(source, body_node)
    for child in body_node.named_children:
        if child.type == "field_declaration":
            visibility = visibility_from_node(source, child)
            type_names = extract_type_names_from_node(source, child_field_map(child).get("type"))
            dependencies.extend(type_names)
            for field_name in _field_declarator_names(source, child):
                fields.append(
                    FieldIR(
                        name=field_name,
                        visibility=visibility,
                        source=SourceRef(relpath=relpath, line=node_line(child)),
                    )
                )
            continue

        if child.type not in {"method_declaration", "constructor_declaration"}:
            continue

        visibility = visibility_from_node(source, child)
        # Java spec: all interface methods are implicitly public.
        if is_interface and visibility == "package":
            visibility = "public"
        field_map = child_field_map(child)
        method_name = node_text(source, field_map.get("name")) or type_name
        return_type_names: tuple[str, ...] = ()
        if child.type == "method_declaration":
            return_type_names = _dedupe_keep_order(extract_type_names_from_node(source, field_map.get("type")))
            dependencies.extend(return_type_names)

        parameter_type_names = _parameter_type_names(source, field_map.get("parameters"))
        dependencies.extend(parameter_type_names)
        methods.append(
            MethodIR(
                name=method_name,
                visibility=visibility,
                source=SourceRef(relpath=relpath, line=node_line(child)),
                return_type_names=return_type_names,
                parameter_type_names=parameter_type_names,
                calls=_collect_method_calls(source, field_map.get("body"), field_types, relpath),
            )
        )

    dependencies = [item for item in _dedupe_keep_order(dependencies) if item != type_name]
    return tuple(fields), tuple(methods), tuple(dependencies)


def parse_java_file_to_ir(file_path: Path, workspace: Path) -> tuple[TypeIR, ...]:
    source, root_node = parse_java_tree(file_path)
    package = _find_package_name(root_node, source)
    relpath = file_path.relative_to(workspace).as_posix()
    output: list[TypeIR] = []

    for node in _top_level_type_nodes(root_node):
        type_name = _declared_type_name(source, node)
        kind = TYPE_NODE_KINDS[node.type]
        fqcn = f"{package}.{type_name}" if package else type_name
        extends_types, implements_types = _extract_parent_types(source, node)
        fields, methods, dependency_types = _collect_members(source, child_field_map(node).get("body"), type_name, relpath, kind)
        output.append(
            TypeIR(
                language="java",
                kind=kind,
                name=type_name,
                package=package,
                fqcn=fqcn,
                source=SourceRef(relpath=relpath, line=node_line(node)),
                extends_types=extends_types,
                implements_types=implements_types,
                dependency_types=dependency_types,
                fields=fields,
                methods=methods,
            )
        )

    return tuple(output)


def index_java_ir(workspace: Path, src_root: Path) -> SourceIndexIR:
    types: list[TypeIR] = []
    for java_file in sorted(path for path in src_root.rglob("*.java") if path.is_file()):
        types.extend(parse_java_file_to_ir(java_file, workspace))
    return SourceIndexIR(language="java", types=tuple(types))
