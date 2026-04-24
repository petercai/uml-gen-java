#!/usr/bin/env python3
"""Shared helpers for Java tree-sitter frontends."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re

from tree_sitter import Language, Node, Parser
import tree_sitter_java


MODIFIERS = {
    "public",
    "protected",
    "private",
    "static",
    "final",
    "abstract",
    "synchronized",
    "native",
    "strictfp",
    "transient",
    "volatile",
    "default",
}

JAVA_PRIMITIVES = {
    "byte",
    "short",
    "int",
    "long",
    "float",
    "double",
    "boolean",
    "char",
    "void",
}


@lru_cache(maxsize=1)
def get_java_language() -> Language:
    return Language(tree_sitter_java.language())


def build_java_parser() -> Parser:
    parser = Parser()
    parser.language = get_java_language()
    return parser


def parse_java_tree(file_path: Path) -> tuple[bytes, Node]:
    source = file_path.read_bytes()
    tree = build_java_parser().parse(source)
    return source, tree.root_node


def node_text(source: bytes, node: Node | None) -> str:
    if node is None:
        return ""
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="ignore")


def node_line(node: Node | None) -> int:
    if node is None:
        return 1
    return node.start_point[0] + 1


def iter_named_descendants(node: Node) -> list[Node]:
    output: list[Node] = []
    for child in node.named_children:
        output.append(child)
        output.extend(iter_named_descendants(child))
    return output


def child_field_map(node: Node) -> dict[str, Node]:
    output: dict[str, Node] = {}
    for index, child in enumerate(node.children):
        field_name = node.field_name_for_child(index)
        if field_name and field_name not in output:
            output[field_name] = child
    return output


def short_type_name(value: str) -> str:
    text = re.sub(r"<[^<>]*>", "", value or "")
    text = text.replace("[]", " ").replace("...", " ").strip()
    if not text:
        return ""
    return text.split(".")[-1]


def extract_type_candidates(type_expr: str) -> list[str]:
    text = re.sub(r"@\w+(?:\([^)]*\))?", " ", type_expr or "")
    text = text.replace("...", " ")
    text = text.replace("[]", " ")
    text = re.sub(r"\bextends\b|\bsuper\b|\?", " ", text)

    names = re.findall(r"[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*", text)
    output: list[str] = []
    seen: set[str] = set()
    for raw in names:
        name = raw.split(".")[-1]
        if name in MODIFIERS or name in JAVA_PRIMITIVES:
            continue
        if name in seen:
            continue
        seen.add(name)
        output.append(name)
    return output


def extract_type_names_from_node(source: bytes, node: Node | None) -> list[str]:
    return extract_type_candidates(node_text(source, node))


def visibility_from_node(source: bytes, node: Node) -> str:
    # Look for a 'modifiers' child first so that annotations before the
    # visibility keyword (e.g. @Override\npublic) are skipped correctly.
    for child in node.children:
        if child.type == "modifiers":
            mod_text = node_text(source, child)
            if re.search(r"\bpublic\b", mod_text):
                return "public"
            if re.search(r"\bprotected\b", mod_text):
                return "protected"
            if re.search(r"\bprivate\b", mod_text):
                return "private"
            return "package"
    # Fallback: no separate modifiers node; check the leading declaration text.
    text = node_text(source, node).lstrip()
    if text.startswith("public "):
        return "public"
    if text.startswith("protected "):
        return "protected"
    if text.startswith("private "):
        return "private"
    return "package"
