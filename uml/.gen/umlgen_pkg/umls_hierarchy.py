#!/usr/bin/env python3
"""Hierarchy helpers for umls source-driven sequence generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class HierarchyPreference:
    """Preferred concrete class mapping derived from defined_hierarchy."""

    by_fqcn: dict[str, str]
    by_short_name: dict[str, str]
    # Ordered chains from most-concrete to least-concrete, keyed by ancestor short name.
    # Used to find the most-concrete class that actually implements a given method.
    chains_by_short_name: dict[str, tuple[str, ...]] = field(default_factory=dict)


def _short_name(type_name: str) -> str:
    text = (type_name or "").strip()
    if not text:
        return ""
    return text.split(".")[-1]


def _resolve_type_name(name: str, *, known_fqcns: dict[str, Any], by_short_name: dict[str, list[str]]) -> str | None:
    text = (name or "").strip()
    if not text:
        return None

    if text in known_fqcns:
        return text

    short = _short_name(text)
    candidates = by_short_name.get(short, [])
    if not candidates:
        return None

    # Deterministic choice for ambiguous short names.
    return sorted(candidates)[0]


def build_defined_hierarchy_preference(
    *,
    known_fqcns: dict[str, Any],
    defined_paths: tuple[tuple[str, ...], ...],
) -> HierarchyPreference:
    """Build ancestor->most-concrete mappings from user-defined hierarchy chains."""
    by_short_name: dict[str, list[str]] = {}
    for fqcn in known_fqcns.keys():
        by_short_name.setdefault(_short_name(fqcn), []).append(fqcn)

    by_fqcn: dict[str, str] = {}
    by_short: dict[str, str] = {}
    chains_by_short: dict[str, tuple[str, ...]] = {}

    for raw_path in defined_paths:
        if len(raw_path) < 2:
            continue

        resolved_path: list[str] = []
        for part in raw_path:
            resolved = _resolve_type_name(part, known_fqcns=known_fqcns, by_short_name=by_short_name)
            if resolved is None:
                resolved_path = []
                break
            resolved_path.append(resolved)

        if len(resolved_path) < 2:
            continue

        concrete = resolved_path[-1]
        # Chain ordered from most-concrete to least-concrete (for method walk-back).
        full_chain_reversed = tuple(reversed(resolved_path))

        for i, ancestor in enumerate(resolved_path[:-1]):
            if ancestor not in by_fqcn:
                by_fqcn[ancestor] = concrete
            ancestor_short = _short_name(ancestor)
            if ancestor_short:
                if ancestor_short not in by_short:
                    by_short[ancestor_short] = concrete
                if ancestor_short not in chains_by_short:
                    # Chain: most-concrete first, stopping at this ancestor (inclusive).
                    chains_by_short[ancestor_short] = full_chain_reversed[: len(resolved_path) - i]

    return HierarchyPreference(by_fqcn=by_fqcn, by_short_name=by_short, chains_by_short_name=chains_by_short)


def _build_type_graph(known_fqcns: dict[str, Any]) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    by_short_name: dict[str, list[str]] = {}
    for fqcn in known_fqcns.keys():
        by_short_name.setdefault(_short_name(fqcn), []).append(fqcn)

    parents_by_child: dict[str, set[str]] = {}
    children_by_parent: dict[str, set[str]] = {}

    for child_fqcn, type_info in known_fqcns.items():
        parents_by_child.setdefault(child_fqcn, set())
        raw_parents = list(getattr(type_info, "extends_types", ()) or ()) + list(
            getattr(type_info, "implements_types", ()) or ()
        )
        for raw_parent in raw_parents:
            parent_resolved = _resolve_type_name(
                raw_parent,
                known_fqcns=known_fqcns,
                by_short_name=by_short_name,
            )
            if parent_resolved is None:
                continue
            parents_by_child[child_fqcn].add(parent_resolved)
            children_by_parent.setdefault(parent_resolved, set()).add(child_fqcn)

    return parents_by_child, children_by_parent


def _connected_component(
    seed: str,
    *,
    parents_by_child: dict[str, set[str]],
    children_by_parent: dict[str, set[str]],
    allowed: set[str],
) -> set[str]:
    component: set[str] = set()
    pending = [seed]

    while pending:
        current = pending.pop()
        if current in component:
            continue
        component.add(current)

        neighbors = set(parents_by_child.get(current, set())) | set(children_by_parent.get(current, set()))
        for neighbor in neighbors:
            if neighbor in allowed and neighbor not in component:
                pending.append(neighbor)

    return component


def _encode_hierarchy_node(
    fqcn: str,
    *,
    nodes: set[str],
    children_by_parent: dict[str, set[str]],
    visiting: set[str],
) -> str | list[Any]:
    name = _short_name(fqcn)
    if fqcn in visiting:
        return name

    children = [child for child in children_by_parent.get(fqcn, set()) if child in nodes]
    if not children:
        return name

    visiting.add(fqcn)
    encoded_children = [
        _encode_hierarchy_node(child, nodes=nodes, children_by_parent=children_by_parent, visiting=visiting)
        for child in sorted(children, key=lambda item: (_short_name(item), item))
    ]
    visiting.remove(fqcn)
    return [name, *encoded_children]


def build_available_type_hierarchy(
    *,
    known_fqcns: dict[str, Any],
    participant_fqcns: set[str],
) -> list[str | list[Any]]:
    """Build whole hierarchy tree for diagram participants (including siblings)."""
    if not participant_fqcns:
        return []

    existing = set(known_fqcns.keys())
    participant_nodes = {fqcn for fqcn in participant_fqcns if fqcn in existing}
    if not participant_nodes:
        return []

    parents_by_child, children_by_parent = _build_type_graph(known_fqcns)

    # Expand each participant to full connected hierarchy component.
    expanded_nodes: set[str] = set()
    for seed in sorted(participant_nodes):
        expanded_nodes |= _connected_component(
            seed,
            parents_by_child=parents_by_child,
            children_by_parent=children_by_parent,
            allowed=existing,
        )

    components: list[set[str]] = []
    remaining = set(expanded_nodes)
    while remaining:
        seed = next(iter(remaining))
        component = _connected_component(
            seed,
            parents_by_child=parents_by_child,
            children_by_parent=children_by_parent,
            allowed=expanded_nodes,
        )
        components.append(component)
        remaining -= component

    output: list[str | list[Any]] = []
    for component in sorted(components, key=lambda c: sorted((_short_name(x), x) for x in c)[0]):
        # Skip isolated nodes (no extends/implements relations) - they have no hierarchy.
        if len(component) == 1:
            sole = next(iter(component))
            if not (parents_by_child.get(sole, set()) & expanded_nodes) and not (children_by_parent.get(sole, set()) & expanded_nodes):
                continue

        roots = [
            fqcn
            for fqcn in component
            if not (parents_by_child.get(fqcn, set()) & component)
        ]
        if not roots:
            roots = sorted(component, key=lambda item: (_short_name(item), item))
        else:
            roots = sorted(roots, key=lambda item: (_short_name(item), item))

        for root in roots:
            output.append(
                _encode_hierarchy_node(
                    root,
                    nodes=component,
                    children_by_parent=children_by_parent,
                    visiting=set(),
                )
            )

    return output


def _format_hierarchy_node_lines(node: str | list[Any], *, depth: int) -> list[str]:
    """Format a single hierarchy node as indented YAML block notation lines.

    depth=0 → '  - Name'  (2-space base indent)
    depth=1 → '    - Name' (4-space indent for first-level children)
    depth=2 → '      - Name' etc.
    """
    indent = " " * (2 + depth * 2)
    if isinstance(node, str):
        return [f"{indent}- {node}"]
    if not isinstance(node, list) or not node:
        return []
    name = node[0]
    lines = [f"{indent}- {name}"]
    for child in node[1:]:
        lines.extend(_format_hierarchy_node_lines(child, depth=depth + 1))
    return lines


def _format_hierarchy_items(items: list[str | list[Any]], *, indent: int = 2) -> list[str]:
    """Format hierarchy items as indented YAML block notation (matches defined_hierarchy style)."""
    lines: list[str] = []
    for item in items:
        lines.extend(_format_hierarchy_node_lines(item, depth=0))
    return lines


def _strip_existing_top_level_section(lines: list[str], section_name: str) -> list[str]:
    output: list[str] = []
    in_block = False

    for line in lines:
        stripped = line.strip()

        if not in_block and stripped.startswith(f"{section_name}:") and not line.startswith(" "):
            in_block = True
            continue

        if in_block:
            if not stripped:
                continue
            if not line.startswith(" ") and ":" in stripped and not stripped.startswith("-"):
                in_block = False
                output.append(line)
            continue

        output.append(line)

    return output


def write_available_type_hierarchy_section(
    config_path: Path,
    hierarchy_items: list[str | list[Any]],
) -> None:
    """Overwrite top-level available_type_hierarchy section in YAML config."""
    existing = config_path.read_text(encoding="utf-8").splitlines()
    cleaned = _strip_existing_top_level_section(existing, "available_type_hierarchy")

    while cleaned and not cleaned[-1].strip():
        cleaned.pop()

    cleaned.append("available_type_hierarchy:")
    if not hierarchy_items:
        cleaned.append("  []")
    else:
        cleaned.extend(_format_hierarchy_items(hierarchy_items, indent=2))

    config_path.write_text("\n".join(cleaned) + "\n", encoding="utf-8")
