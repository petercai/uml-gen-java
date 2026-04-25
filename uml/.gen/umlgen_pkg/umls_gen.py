#!/usr/bin/env python3
"""Generate source-driven PlantUML sequence diagrams from Java source."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re

from umlgen_pkg.java_sequence_index import MethodDef, SequenceIndex, index_source_tree
from umlgen_pkg.umlgen_cli import HelpOnErrorParser
from umlgen_pkg.umlgen_file_header import prepend_plantuml_header, read_mark_file
from umlgen_pkg.umlgen_legend import insert_legend_block
from umlgen_pkg.umlgen_matched import write_matched_section
from umlgen_pkg.umlgen_rule_match import looks_like_regex_rule, rule_matches_type
from umlgen_pkg.umlgen_yaml import ConfigError, SequenceConfig, load_diagram_config
from umlgen_pkg.umls_hierarchy import (
    HierarchyPreference,
    build_available_type_hierarchy,
    build_defined_hierarchy_preference,
    write_available_type_hierarchy_section,
)
from umlgen_pkg.frontends.registry import resolve_java_frontend


def _merge_sequence_indexes(indexes: list[SequenceIndex]) -> SequenceIndex:
    """Merge multiple SequenceIndex objects into one (later entries win on key conflict)."""
    types_by_fqcn: dict = {}
    methods_by_key: dict = {}
    methods_by_short_type: dict = {}
    for idx in indexes:
        types_by_fqcn.update(idx.types_by_fqcn)
        methods_by_key.update(idx.methods_by_key)
        for key, methods in idx.methods_by_short_type.items():
            methods_by_short_type.setdefault(key, []).extend(methods)
    return SequenceIndex(
        types_by_fqcn=types_by_fqcn,
        methods_by_key=methods_by_key,
        methods_by_short_type=methods_by_short_type,
    )


@dataclass(frozen=True)
class SequenceEdge:
    caller: MethodDef
    callee: MethodDef
    caller_call_line: int


_UMLS_EPILOG = """
MANDATORY:
  --config CONFIG   Path to the sequence YAML config file (REQUIRED)

Examples:
  umls_gen.py --config uml/umls-DummyController.yaml
  umls_gen.py --config uml/umls-DummyController.yaml --workspace /path/to/project
"""


def parse_args() -> argparse.Namespace:
    parser = HelpOnErrorParser(
        description="Generate source-driven PlantUML sequence diagrams from Java source",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=_UMLS_EPILOG,
    )
    parser.add_argument("--config", required=True, help="Path to sequence yaml config (REQUIRED)")
    parser.add_argument("--workspace", default=".", help="Workspace root")
    return parser.parse_args()


def resolve_methods_by_rule(
    *,
    rule: str,
    index: SequenceIndex,
    workspace: Path,
) -> list[MethodDef]:
    matched: list[MethodDef] = []

    if ":" in rule:
        left, right = rule.rsplit(":", 1)
        left = left.strip()
        right = right.strip()
        if not right:
            return []

        for method in index.methods_by_key.values():
            if method.method_name != right:
                continue
            type_info = index.types_by_fqcn.get(method.type_fqcn)
            if type_info is None:
                continue
            abs_path = workspace / method.relpath
            if rule_matches_type(
                rule=left,
                fqcn=method.type_fqcn,
                short_name=method.type_short_name,
                relpath=method.relpath,
                absolute_path=abs_path,
                workspace=workspace,
            ):
                matched.append(method)

        return matched

    for method in index.methods_by_key.values():
        type_info = index.types_by_fqcn.get(method.type_fqcn)
        if type_info is None:
            continue
        abs_path = workspace / method.relpath
        if rule_matches_type(
            rule=rule,
            fqcn=method.type_fqcn,
            short_name=method.type_short_name,
            relpath=method.relpath,
            absolute_path=abs_path,
            workspace=workspace,
        ):
            matched.append(method)

    return matched


def method_matches_exclude(method: MethodDef, excludes: tuple[str, ...], workspace: Path) -> bool:
    for rule in excludes:
        text = rule.strip()
        if not text:
            continue

        if ":" in text:
            left, right = text.rsplit(":", 1)
            left = left.strip()
            right = right.strip()
            if right and method.method_name != right:
                continue
            if rule_matches_type(
                rule=left,
                fqcn=method.type_fqcn,
                short_name=method.type_short_name,
                relpath=method.relpath,
                absolute_path=workspace / method.relpath,
                workspace=workspace,
            ):
                return True
            continue

        if looks_like_regex_rule(text):
            regex = re.compile(text)
            target = f"{method.type_fqcn}.{method.method_name}"
            if regex.search(target) or regex.search(method.method_name):
                return True
            continue

        if rule_matches_type(
            rule=text,
            fqcn=method.type_fqcn,
            short_name=method.type_short_name,
            relpath=method.relpath,
            absolute_path=workspace / method.relpath,
            workspace=workspace,
        ):
            return True

    return False


def resolve_callee(
    *,
    caller: MethodDef,
    qualifier: str | None,
    method_name: str,
    index: SequenceIndex,
    hierarchy_preference: HierarchyPreference,
) -> MethodDef | None:
    if qualifier:
        # Walk the defined hierarchy chain from most-concrete to least-concrete.
        # This ensures calls to interfaces/abstract classes are resolved to the
        # concrete implementation that actually owns the method.
        chain = hierarchy_preference.chains_by_short_name.get(qualifier)
        if chain:
            for fqcn in chain:
                preferred = index.methods_by_key.get((fqcn, method_name))
                if preferred is not None:
                    return preferred

        # Fallback: try the single most-concrete class even without method match above.
        preferred_fqcn = hierarchy_preference.by_short_name.get(qualifier)
        if preferred_fqcn:
            preferred = index.methods_by_key.get((preferred_fqcn, method_name))
            if preferred is not None:
                return preferred

        # Prefer direct short-name class match.
        for candidate in index.methods_by_short_type.get(qualifier, []):
            if candidate.method_name == method_name:
                preferred_fqcn = hierarchy_preference.by_fqcn.get(candidate.type_fqcn)
                if preferred_fqcn:
                    preferred = index.methods_by_key.get((preferred_fqcn, method_name))
                    if preferred is not None:
                        return preferred
                return candidate

    # Same-class call fallback.
    same_class = index.methods_by_key.get((caller.type_fqcn, method_name))
    if same_class is not None:
        return same_class

    # Global fallback by method name only when unique.
    candidates = [item for item in index.methods_by_key.values() if item.method_name == method_name]
    if len(candidates) == 1:
        return candidates[0]
    return None


def build_call_chain(
    *,
    roots: list[MethodDef],
    excludes: tuple[str, ...],
    max_cross_class_depth: int,
    index: SequenceIndex,
    workspace: Path,
    hierarchy_preference: HierarchyPreference,
) -> list[SequenceEdge]:
    seen_depth: dict[tuple[str, str], int] = {
        (root.type_fqcn, root.method_name): 0 for root in roots
    }
    edges: list[SequenceEdge] = []

    def walk(caller: MethodDef, depth: int) -> None:
        for call in caller.calls:
            callee = resolve_callee(
                caller=caller,
                qualifier=call.qualifier,
                method_name=call.method_name,
                index=index,
                hierarchy_preference=hierarchy_preference,
            )
            if callee is None:
                continue
            if method_matches_exclude(callee, excludes, workspace):
                continue

            cross_class = 1 if callee.type_fqcn != caller.type_fqcn else 0
            next_depth = depth + cross_class
            if next_depth > max_cross_class_depth:
                continue

            edges.append(SequenceEdge(caller=caller, callee=callee, caller_call_line=call.call_line))

            key = (callee.type_fqcn, callee.method_name)
            previous = seen_depth.get(key)
            if previous is None or next_depth < previous:
                seen_depth[key] = next_depth
                walk(callee, next_depth)

    for root in roots:
        walk(root, 0)

    return edges


def build_call_chain_for_root(
    *,
    root: MethodDef,
    excludes: tuple[str, ...],
    max_cross_class_depth: int,
    index: SequenceIndex,
    workspace: Path,
    hierarchy_preference: HierarchyPreference,
) -> list[SequenceEdge]:
    """Build depth-first call chain for a single root, independent of other roots."""
    seen_depth: dict[tuple[str, str], int] = {
        (root.type_fqcn, root.method_name): 0
    }
    edges: list[SequenceEdge] = []

    def walk(caller: MethodDef, depth: int) -> None:
        for call in caller.calls:
            callee = resolve_callee(
                caller=caller,
                qualifier=call.qualifier,
                method_name=call.method_name,
                index=index,
                hierarchy_preference=hierarchy_preference,
            )
            if callee is None:
                continue
            if method_matches_exclude(callee, excludes, workspace):
                continue

            cross_class = 1 if callee.type_fqcn != caller.type_fqcn else 0
            next_depth = depth + cross_class
            if next_depth > max_cross_class_depth:
                continue

            edges.append(SequenceEdge(caller=caller, callee=callee, caller_call_line=call.call_line))

            key = (callee.type_fqcn, callee.method_name)
            previous = seen_depth.get(key)
            if previous is None or next_depth < previous:
                seen_depth[key] = next_depth
                walk(callee, next_depth)

    walk(root, 0)
    return edges


def sanitize_alias(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", value)
    if not cleaned:
        return "participant"
    if cleaned[0].isdigit():
        return f"P_{cleaned}"
    return cleaned


def method_key(method: MethodDef) -> tuple[str, str]:
    return (method.type_fqcn, method.method_name)


def find_entry_methods(roots: list[MethodDef], edges: list[SequenceEdge]) -> list[MethodDef]:
    called_by_other: set[tuple[str, str]] = set()
    for edge in edges:
        caller_key = method_key(edge.caller)
        callee_key = method_key(edge.callee)
        if caller_key != callee_key:
            called_by_other.add(callee_key)

    return [root for root in roots if method_key(root) not in called_by_other]


def build_matched_entries(
    *,
    roots: list[MethodDef],
    edges: list[SequenceEdge],
    entry_methods: list[MethodDef],
    index: SequenceIndex,
) -> list[str]:
    class_paths: set[str] = set()
    called_methods: set[str] = set()

    for method in roots:
        class_paths.add(method.relpath)

    for edge in edges:
        class_paths.add(edge.caller.relpath)
        class_paths.add(edge.callee.relpath)
        called_methods.add(f"{edge.callee.relpath}:{edge.callee.method_name}")

    for method in entry_methods:
        class_paths.add(method.relpath)
        called_methods.add(f"{method.relpath}:{method.method_name}")

    # Keep this guard for forward-compatibility with custom indexers.
    for fqcn, type_info in index.types_by_fqcn.items():
        _ = fqcn
        _ = type_info

    return sorted(class_paths | called_methods)


def build_sequence_puml(
    per_root_chains: list[tuple[MethodDef, list[SequenceEdge]]],
    output_stem: str,
    index: SequenceIndex,
) -> str:
    """Build PlantUML sequence diagram with depth-first per-root call ordering.

    Each entry method's full call sub-tree is emitted before the next entry
    method's actor call, matching natural depth-first reading order.
    autoactivate is intentionally disabled: enabling it requires explicit
    deactivation calls at every return site, which is not supported here.
    """
    participants: dict[str, str] = {}

    def add_participant(fqcn: str, short_name: str) -> None:
        if fqcn not in participants:
            participants[fqcn] = short_name

    for root, sub_edges in per_root_chains:
        add_participant(root.type_fqcn, root.type_short_name)
        for edge in sub_edges:
            add_participant(edge.caller.type_fqcn, edge.caller.type_short_name)
            add_participant(edge.callee.type_fqcn, edge.callee.type_short_name)

    alias_map: dict[str, str] = {}
    ordered_participants = list(participants.items())
    for i, (fqcn, short_name) in enumerate(ordered_participants, start=1):
        alias_map[fqcn] = f"{sanitize_alias(short_name)}_{i}"

    lines: list[str] = [
        f"@startuml {output_stem}",
        "hide footbox",
        "skinparam ParticipantPadding 20",
        "skinparam BoxPadding 10",
        "' autoactivate on",
        "",
        'actor "Actor" as Actor_0',
    ]

    for fqcn, short_name in ordered_participants:
        type_info = index.types_by_fqcn.get(fqcn)
        if type_info is None:
            continue
        label = f"{short_name}:\\n{short_name}"
        lines.append(
            f'participant "{label}" as {alias_map[fqcn]} [[{type_info.relpath}:{type_info.decl_line}]]'
        )

    lines.append("")

    # Emit depth-first per-root: actor->entry, then all sub-calls in DFS order.
    for root, sub_edges in per_root_chains:
        callee_alias = alias_map[root.type_fqcn]
        callee_label = f"{Path(root.relpath).name}:{root.decl_line}"
        message_text = (
            f"{root.method_name}()"
            f"\\ncallee:[[{root.relpath}:{root.decl_line} {callee_label}]]"
            "\\ncaller:[entry include-order]"
        )
        lines.append(f"Actor_0 -> {callee_alias} : {message_text}")

        for edge in sub_edges:
            caller_alias = alias_map[edge.caller.type_fqcn]
            callee_alias = alias_map[edge.callee.type_fqcn]
            callee_label = f"{Path(edge.callee.relpath).name}:{edge.callee.decl_line}"
            caller_label = f"{Path(edge.caller.relpath).name}:{edge.caller_call_line}"
            message_text = (
                f"{edge.callee.method_name}()"
                f"\\ncallee:[[{edge.callee.relpath}:{edge.callee.decl_line} {callee_label}]]"
                f"\\ncaller:[[{edge.caller.relpath}:{edge.caller_call_line} {caller_label}]]"
            )
            lines.append(f"{caller_alias} -> {callee_alias} : {message_text}")

    lines.append("@enduml")
    return "\n".join(lines) + "\n"


def load_entry_methods(config: SequenceConfig, index: SequenceIndex, workspace: Path) -> list[MethodDef]:
    matched: list[MethodDef] = []
    for rule in config.include:
        matched.extend(resolve_methods_by_rule(rule=rule, index=index, workspace=workspace))

    deduped: dict[tuple[str, str], MethodDef] = {}
    for method in matched:
        key = (method.type_fqcn, method.method_name)
        if key not in deduped:
            deduped[key] = method

    filtered = [method for method in deduped.values() if not method_matches_exclude(method, config.exclude, workspace)]
    return filtered


def main() -> int:
    args = parse_args()
    workspace = Path(args.workspace).resolve()

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = (workspace / config_path).resolve()

    config = load_diagram_config(config_path)
    if config.diagram_type != "sequence" or config.sequence_config is None:
        raise ConfigError("Config diagram.type must be sequence for umls_gen.py")

    sequence_config = config.sequence_config
    parser_name = sequence_config.runtime.parser
    try:
        frontend = resolve_java_frontend(parser_name)
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc

    src_roots = [workspace / r for r in sequence_config.src_roots]
    indexes: list[SequenceIndex] = []
    for src_root in src_roots:
        src_root_resolved = src_root.resolve()
        if not src_root_resolved.exists():
            print(f"[WARN] src_root does not exist, skipping: {src_root_resolved}")
            continue
        if parser_name == "legacy":
            indexes.append(index_source_tree(workspace, src_root_resolved))
        else:
            indexes.append(frontend.sequence_indexer(workspace, src_root_resolved))

    if not indexes:
        print("[WARN] No valid src_root paths found; aborting")
        return 1

    index = _merge_sequence_indexes(indexes) if len(indexes) > 1 else indexes[0]

    roots = load_entry_methods(sequence_config, index, workspace)

    hierarchy_preference = build_defined_hierarchy_preference(
        known_fqcns=index.types_by_fqcn,
        defined_paths=sequence_config.defined_hierarchy_paths,
    )

    if not roots:
        write_available_type_hierarchy_section(config_path, [])
        write_matched_section(config_path, [])
        print("[WARN] include/exclude resolved no root methods; matched section updated")
        return 0

    edges = build_call_chain(
        roots=roots,
        excludes=sequence_config.exclude,
        max_cross_class_depth=sequence_config.depth,
        index=index,
        workspace=workspace,
        hierarchy_preference=hierarchy_preference,
    )

    entry_methods = find_entry_methods(roots, edges)
    matched = build_matched_entries(
        roots=roots,
        edges=edges,
        entry_methods=entry_methods,
        index=index,
    )

    participant_fqcns = {
        edge.caller.type_fqcn for edge in edges
    } | {
        edge.callee.type_fqcn for edge in edges
    } | {
        method.type_fqcn for method in roots
    } | {
        method.type_fqcn for method in entry_methods
    }
    available_hierarchy = build_available_type_hierarchy(
        known_fqcns=index.types_by_fqcn,
        participant_fqcns=participant_fqcns,
    )
    write_available_type_hierarchy_section(config_path, available_hierarchy)
    write_matched_section(config_path, matched)

    # Build per-root depth-first chains for ordered output.
    entry_keys = {method_key(m) for m in entry_methods}
    per_root_chains: list[tuple[MethodDef, list[SequenceEdge]]] = [
        (
            root,
            build_call_chain_for_root(
                root=root,
                excludes=sequence_config.exclude,
                max_cross_class_depth=sequence_config.depth,
                index=index,
                workspace=workspace,
                hierarchy_preference=hierarchy_preference,
            ),
        )
        for root in roots
        if method_key(root) in entry_keys
    ]

    output = sequence_config.output
    if not output:
        output = f"uml/plantuml/umls-{roots[0].type_short_name}.puml"

    output_path = Path(output)
    if not output_path.is_absolute():
        output_path = (workspace / output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    diagram_name = output_path.stem
    puml = build_sequence_puml(per_root_chains, diagram_name, index)
    header_text = read_mark_file(__file__)
    puml_with_header = prepend_plantuml_header(puml, header_text)
    puml_with_header = insert_legend_block(puml_with_header, config_path, workspace)
    output_path.write_text(puml_with_header, encoding="utf-8")
    print(f"[OK] Generated {output_path}")
    if sequence_config.observability.emit_summary:
        print(
            f"[OK] parser={sequence_config.runtime.parser} roots={len(roots)} edges={len(edges)} depth={sequence_config.depth}"
        )
    else:
        print(f"[OK] roots={len(roots)} edges={len(edges)} depth={sequence_config.depth}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
