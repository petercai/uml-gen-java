#!/usr/bin/env python3
"""Generate PlantUML class diagrams from Java source using YAML rules."""

from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from umlgen_cli import HelpOnErrorParser
from umlgen_file_header import prepend_plantuml_header, read_mark_file
from umlgen_legend import insert_legend_block
from umlgen_matched import write_matched_section
from umlgen_rule_match import rule_matches_type
from umlgen_yaml import ClassConfig, ConfigError, load_diagram_config
from frontends.registry import resolve_java_frontend

PACKAGE_RE = re.compile(r"^\s*package\s+([A-Za-z_$][\w$.]*)\s*;")
TYPE_DECL_RE = re.compile(
    r"^\s*(?:public|protected|private)?\s*(?:abstract\s+|final\s+)?"
    r"(class|interface|enum|record)\s+([A-Za-z_$][\w$]*)\b([^\{;]*)"
)
METHOD_RE = re.compile(r"([A-Za-z_$][\w$]*)\s*\(([^)]*)\)")
FIELD_RE = re.compile(r"^\s*(?:public|protected|private)?\s*(?:static\s+)?(?:final\s+)?(.+?)\s+([A-Za-z_$][\w$]*)\s*(?:=|;|,)")

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


_UMLC_EPILOG = """
MANDATORY (one of):
  --config CONFIG       YAML config file driving include/exclude/depth/output
                        (RECOMMENDED: enables legend, matched section, etc.)
  --input FILE_OR_CLASS One or more Java files, directories, or class names

Examples:
  umlc_gen.py --config uml/umlc-DummyController.yaml
  umlc_gen.py --input src/main/java/com/example/MyService.java
  umlc_gen.py --input MyService --depth 3
"""


def parse_args() -> argparse.Namespace:
    parser = HelpOnErrorParser(
        description="Generate PlantUML class diagrams from Java source",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=_UMLC_EPILOG,
    )
    parser.add_argument("--config", help="YAML config path (recommended)")
    parser.add_argument("--workspace", default=os.getcwd(), help="Workspace root")
    parser.add_argument("--input", nargs="+", help="Fallback input Java files or class names")
    parser.add_argument("--depth", type=int, default=2, help="Fallback depth")
    parser.add_argument("--output-dir", default="uml/plantuml", help="Fallback output dir (default: uml/plantuml)")
    parser.add_argument("--update-target-puml", help="Fallback merged output puml path")
    args = parser.parse_args()
    if not args.config and not args.input:
        parser.error("--config or --input is required")
    return args


def dedupe_keep_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def strip_inline_comment(line: str) -> str:
    marker = line.find("//")
    if marker == -1:
        return line
    return line[:marker]


def short_type(value: str) -> str:
    text = re.sub(r"<[^<>]*>", "", value or "")
    text = text.replace("[]", "").strip()
    if not text:
        return ""
    return text.split(".")[-1]


def extract_type_candidates(type_expr: str) -> list[str]:
    text = re.sub(r"@\w+(?:\([^)]*\))?", " ", type_expr)
    text = text.replace("...", " ")
    text = text.replace("[]", " ")
    text = re.sub(r"\bextends\b|\bsuper\b|\?", " ", text)

    names = re.findall(r"[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*", text)
    output: list[str] = []
    for raw in names:
        name = raw.split(".")[-1]
        if name in MODIFIERS or name in JAVA_PRIMITIVES:
            continue
        output.append(name)
    return dedupe_keep_order(output)


def parse_decl_parents(tail: str) -> tuple[list[str], list[str]]:
    extends_types: list[str] = []
    implements_types: list[str] = []

    ext = re.search(r"\bextends\s+([^\{]+?)(?:\bimplements\b|$)", tail)
    if ext:
        extends_types.extend(extract_type_candidates(ext.group(1)))

    impl = re.search(r"\bimplements\s+([^\{]+)$", tail)
    if impl:
        implements_types.extend(extract_type_candidates(impl.group(1)))

    return dedupe_keep_order(extends_types), dedupe_keep_order(implements_types)


def visibility_from_line(line: str) -> str:
    text = line.strip()
    if text.startswith("public "):
        return "public"
    if text.startswith("protected "):
        return "protected"
    if text.startswith("private "):
        return "private"
    return "package"


def parse_methods_and_fields(lines: list[str], start: int, end: int, type_name: str, type_kind: str = "class") -> tuple[list[FieldInfo], list[MethodInfo], list[str]]:
    fields: list[FieldInfo] = []
    methods: list[MethodInfo] = []
    dependencies: list[str] = []
    depth = 0
    is_interface = type_kind == "interface"

    i = start
    while i <= end:
        raw = strip_inline_comment(lines[i])
        current_depth = depth
        text = raw.strip()

        if i == start:
            for ch in raw:
                if ch == "{":
                    depth += 1
                elif ch == "}" and depth > 0:
                    depth -= 1
            i += 1
            continue

        if current_depth == 1 and text and not text.startswith(("@", "//", "/*", "*")):
            field_match = FIELD_RE.match(text)
            if field_match and "(" not in text and ")" not in text:
                visibility = visibility_from_line(text)
                tokens = set(text.split())
                if not ("static" in tokens and "final" in tokens):
                    fields.append(FieldInfo(name=field_match.group(2), visibility=visibility, line=i + 1))
                dependencies.extend(extract_type_candidates(field_match.group(1)))
            else:
                signature = text
                sig_end = i
                while "(" in signature and ")" not in signature and sig_end + 1 <= end:
                    sig_end += 1
                    signature += " " + strip_inline_comment(lines[sig_end]).strip()

                method_match = METHOD_RE.search(signature)
                # Java interfaces: abstract method declarations end with ";"
                # (implicitly public abstract). Default methods have a body.
                # Classes: exclude abstract declarations (end with ";") to avoid
                # showing abstract stubs without a body.
                is_method_decl = method_match and (is_interface or not signature.endswith(";"))
                if is_method_decl:
                    name = method_match.group(1)
                    if re.match(r"^[A-Za-z_$][\w$]*$", name):
                        visibility = visibility_from_line(signature)
                        # Java interface methods are implicitly public when no modifier is given.
                        if is_interface and visibility == "package":
                            visibility = "public"
                        methods.append(MethodInfo(name=name, visibility=visibility, line=i + 1))

                        # return type and params for dependency extraction
                        prefix = signature.split("(", 1)[0]
                        tokens = [tok for tok in re.split(r"\s+", prefix) if tok and tok not in MODIFIERS]
                        if tokens and tokens[-1] == name:
                            dependencies.extend(extract_type_candidates(" ".join(tokens[:-1])))

                        params = method_match.group(2)
                        for part in params.split(","):
                            chunk = part.strip()
                            if not chunk:
                                continue
                            words = [w for w in re.split(r"\s+", chunk) if w and not w.startswith("@")]
                            words = [w for w in words if w not in MODIFIERS]
                            if len(words) >= 2:
                                dependencies.extend(extract_type_candidates(" ".join(words[:-1])))

        for ch in raw:
            if ch == "{":
                depth += 1
            elif ch == "}" and depth > 0:
                depth -= 1
        i += 1

    dependencies = [item for item in dependencies if item and item != type_name]
    return fields, methods, dedupe_keep_order(dependencies)


def find_package(lines: list[str]) -> str:
    for line in lines:
        matched = PACKAGE_RE.match(line)
        if matched:
            return matched.group(1)
    return ""


def find_type_block_end(lines: list[str], start_idx: int) -> int:
    depth = 0
    opened = False
    for idx in range(start_idx, len(lines)):
        line = strip_inline_comment(lines[idx])
        for ch in line:
            if ch == "{":
                depth += 1
                opened = True
            elif ch == "}" and opened:
                depth -= 1
        if opened and depth == 0:
            return idx
    return len(lines) - 1


def parse_java_file(file_path: Path, workspace: Path) -> list[JavaTypeInfo]:
    lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    package = find_package(lines)
    out: list[JavaTypeInfo] = []

    for i, line in enumerate(lines):
        matched = TYPE_DECL_RE.match(strip_inline_comment(line))
        if not matched:
            continue

        kind = matched.group(1)
        name = matched.group(2)
        tail = matched.group(3).strip()
        end = find_type_block_end(lines, i)

        extends_types, implements_types = parse_decl_parents(tail)
        fields, methods, dependency_types = parse_methods_and_fields(lines, i, end, name, kind)

        fqcn = f"{package}.{name}" if package else name
        relpath = file_path.relative_to(workspace).as_posix()
        out.append(
            JavaTypeInfo(
                kind=kind,
                name=name,
                package=package,
                fqcn=fqcn,
                decl_line=i + 1,
                file_path=file_path,
                relpath=relpath,
                extends_types=extends_types,
                implements_types=implements_types,
                dependency_types=dependency_types,
                fields=fields,
                methods=methods,
            )
        )

    return out


def index_workspace_types(workspace: Path, src_root: Path) -> tuple[dict[str, JavaTypeInfo], dict[str, list[JavaTypeInfo]]]:
    by_fqcn: dict[str, JavaTypeInfo] = {}
    by_simple: dict[str, list[JavaTypeInfo]] = {}

    for java_file in sorted(p for p in src_root.rglob("*.java") if p.is_file()):
        for info in parse_java_file(java_file, workspace):
            by_fqcn[info.fqcn] = info
            by_simple.setdefault(info.name, []).append(info)

    return by_fqcn, by_simple


def resolve_local_type(raw: str, current: JavaTypeInfo, by_fqcn: dict[str, JavaTypeInfo], by_simple: dict[str, list[JavaTypeInfo]]) -> JavaTypeInfo | None:
    if not raw:
        return None
    if raw in by_fqcn:
        return by_fqcn[raw]

    short = raw.split(".")[-1]
    candidates = by_simple.get(short, [])
    if not candidates:
        return None

    package_matches = [item for item in candidates if item.package == current.package]
    if len(package_matches) == 1:
        return package_matches[0]
    if len(candidates) == 1:
        return candidates[0]
    return None


def expand_types_by_depth(root: JavaTypeInfo, depth: int, by_fqcn: dict[str, JavaTypeInfo], by_simple: dict[str, list[JavaTypeInfo]]) -> tuple[set[str], dict[str, int]]:
    included: set[str] = {root.fqcn}
    levels: dict[str, int] = {root.fqcn: 0}
    frontier: list[JavaTypeInfo] = [root]

    for current_depth in range(1, max(depth, 0) + 1):
        next_frontier: list[JavaTypeInfo] = []
        for node in frontier:
            ordered = node.extends_types + node.implements_types + node.dependency_types
            for raw in ordered:
                target = resolve_local_type(raw, node, by_fqcn, by_simple)
                if target is None or target.fqcn in included:
                    continue
                included.add(target.fqcn)
                levels[target.fqcn] = current_depth
                next_frontier.append(target)
        frontier = next_frontier

    return included, levels


def topo_parent_first(included: set[str], by_fqcn: dict[str, JavaTypeInfo], by_simple: dict[str, list[JavaTypeInfo]]) -> list[JavaTypeInfo]:
    indegree = {fqcn: 0 for fqcn in included}
    children = {fqcn: [] for fqcn in included}

    for fqcn in included:
        node = by_fqcn[fqcn]
        for raw in node.extends_types + node.implements_types:
            parent = resolve_local_type(raw, node, by_fqcn, by_simple)
            if parent is None or parent.fqcn not in included:
                continue
            children[parent.fqcn].append(node.fqcn)
            indegree[node.fqcn] += 1

    queue = sorted([fqcn for fqcn, degree in indegree.items() if degree == 0])
    out: list[JavaTypeInfo] = []

    while queue:
        current = queue.pop(0)
        out.append(by_fqcn[current])
        for child in sorted(children[current]):
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
                queue.sort()

    remaining = [fqcn for fqcn in sorted(included) if fqcn not in {node.fqcn for node in out}]
    for fqcn in remaining:
        out.append(by_fqcn[fqcn])
    return out


def visibility_symbol(visibility: str) -> str:
    if visibility == "public":
        return "+"
    if visibility == "protected":
        return "#"
    if visibility == "private":
        return "-"
    return "~"


def allowed_method(method: MethodInfo, scope: str) -> bool:
    if scope == "all":
        return True
    return method.visibility in {"public", "protected"}


def render_type_block(info: JavaTypeInfo, method_scope: str, member_scope: str) -> list[str]:
    header_keyword = "class"
    if info.kind == "interface":
        header_keyword = "interface"
    elif info.kind == "enum":
        header_keyword = "enum"

    header = f"{header_keyword} {info.name} [[{info.relpath}:{info.decl_line}]]"
    body: list[str] = []

    if member_scope == "all":
        for field_info in info.fields:
            body.append(
                f"  {visibility_symbol(field_info.visibility)} [[{info.relpath}:{field_info.line} {field_info.name}]]"
            )

    filtered_methods = [method for method in info.methods if allowed_method(method, method_scope)]
    for method in filtered_methods:
        body.append(f"  {visibility_symbol(method.visibility)} [[{info.relpath}:{method.line} {method.name}()]]")

    if not body:
        return [header]

    return [f"{header} {{", *body, "}"]


def build_edges(included: set[str], by_fqcn: dict[str, JavaTypeInfo], by_simple: dict[str, list[JavaTypeInfo]]) -> list[str]:
    edges: list[str] = []

    for fqcn in sorted(included):
        node = by_fqcn[fqcn]

        for raw in node.extends_types:
            parent = resolve_local_type(raw, node, by_fqcn, by_simple)
            if parent and parent.fqcn in included:
                edges.append(f"{node.name} --|> {parent.name}")

        for raw in node.implements_types:
            parent = resolve_local_type(raw, node, by_fqcn, by_simple)
            if parent and parent.fqcn in included:
                edges.append(f"{node.name} ..|> {parent.name}")

        parent_short = set(node.extends_types + node.implements_types)
        for raw in node.dependency_types:
            if raw in parent_short:
                continue
            target = resolve_local_type(raw, node, by_fqcn, by_simple)
            if target and target.fqcn in included:
                edges.append(f"{node.name} --> {target.name}")

    return dedupe_keep_order(edges)


def build_puml(*, roots: list[JavaTypeInfo], ordered: list[JavaTypeInfo], edges: list[str], levels: dict[str, int], depth: int, method_scope: str, member_scope: str, diagram_name: str) -> str:
    _ = levels
    _ = roots

    lines: list[str] = [
        f"@startuml {diagram_name}",
        "' Generated by umlc_gen.py",
        f"' Depth: {depth}",
        "top to bottom direction",
        "hide empty members",
        "",
    ]

    for info in ordered:
        lines.extend(render_type_block(info, method_scope, member_scope))

    lines.append("")
    lines.extend(edges)
    lines.append("@enduml")
    return "\n".join(lines) + "\n"


def resolve_roots_from_rules(
    *,
    rules: tuple[str, ...],
    workspace: Path,
    by_fqcn: dict[str, JavaTypeInfo],
) -> set[str]:
    matched: set[str] = set()
    for rule in rules:
        for fqcn, info in by_fqcn.items():
            if rule_matches_type(
                rule=rule,
                fqcn=fqcn,
                short_name=info.name,
                relpath=info.relpath,
                absolute_path=info.file_path,
                workspace=workspace,
            ):
                matched.add(fqcn)
    return matched


def resolve_input_files(input_args: list[str], workspace: Path) -> list[Path]:
    files: list[Path] = []
    for raw in input_args:
        value = raw.strip()
        if not value:
            continue

        path = Path(value)
        if not path.is_absolute():
            path = (workspace / path).resolve()

        if path.is_file() and path.suffix == ".java":
            files.append(path)
            continue

        if path.is_dir():
            files.extend(sorted(p for p in path.rglob("*.java") if p.is_file()))
            continue

        simple = value.split(".")[-1]
        files.extend(sorted(p for p in workspace.rglob(f"{simple}.java") if p.is_file()))

    unique = dedupe_keep_order(str(path) for path in files)
    return [Path(path) for path in unique]


def determine_root_for_file(file_path: Path, by_fqcn: dict[str, JavaTypeInfo]) -> JavaTypeInfo | None:
    candidates = [info for info in by_fqcn.values() if info.file_path == file_path]
    if not candidates:
        return None
    exact = [item for item in candidates if item.name == file_path.stem]
    return exact[0] if exact else candidates[0]


def build_reverse_index(
    by_fqcn: dict[str, JavaTypeInfo],
    by_simple: dict[str, list[JavaTypeInfo]],
) -> dict[str, list[str]]:
    """Build a parent-FQCN → [child-FQCNs] reverse index for hierarchy expansion."""
    reverse: dict[str, list[str]] = {}
    for fqcn, info in by_fqcn.items():
        for raw in info.extends_types + info.implements_types:
            parent = resolve_local_type(raw, info, by_fqcn, by_simple)
            if parent is not None:
                reverse.setdefault(parent.fqcn, []).append(fqcn)
    return reverse


def expand_interface_hierarchy(
    root_fqcn: str,
    by_fqcn: dict[str, JavaTypeInfo],
    reverse_index: dict[str, list[str]],
) -> set[str]:
    """Return the complete downward hierarchy for an interface root.

    Includes the root itself, all direct and transitive sub-interfaces, all
    implementing classes, and their sub-classes recursively.
    """
    result: set[str] = {root_fqcn}
    frontier = [root_fqcn]
    while frontier:
        current = frontier.pop()
        for child_fqcn in sorted(reverse_index.get(current, [])):
            if child_fqcn not in result and child_fqcn in by_fqcn:
                result.add(child_fqcn)
                frontier.append(child_fqcn)
    return result


def merge_expansions(roots: list[JavaTypeInfo], depth: int, by_fqcn: dict[str, JavaTypeInfo], by_simple: dict[str, list[JavaTypeInfo]], reverse_index: dict[str, list[str]] | None = None) -> tuple[set[str], dict[str, int]]:
    included: set[str] = set()
    levels: dict[str, int] = {}

    for root in roots:
        one_included, one_levels = expand_types_by_depth(root, depth, by_fqcn, by_simple)
        included.update(one_included)
        for fqcn, level in one_levels.items():
            previous = levels.get(fqcn)
            if previous is None or level < previous:
                levels[fqcn] = level

    # For interface roots: unconditionally expand the full sub-type hierarchy
    # (all sub-interfaces, all implementing classes, and their sub-classes).
    if reverse_index is not None:
        for root in roots:
            if root.kind == "interface":
                hierarchy = expand_interface_hierarchy(root.fqcn, by_fqcn, reverse_index)
                for fqcn in hierarchy:
                    if fqcn not in included:
                        included.add(fqcn)
                        levels[fqcn] = 0

    return included, levels


def main() -> int:
    args = parse_args()
    workspace = Path(args.workspace).resolve()
    header_text = read_mark_file(__file__)

    class_config: ClassConfig | None = None
    config_path: Path | None = None
    if args.config:
        config_path = Path(args.config)
        if not config_path.is_absolute():
            config_path = (workspace / config_path).resolve()
        config = load_diagram_config(config_path)
        if config.diagram_type != "class" or config.class_config is None:
            raise ConfigError("Config diagram.type must be class for umlc_gen.py")
        class_config = config.class_config

    src_roots_raw = [workspace / "src/main/java"]
    if class_config is not None:
        src_roots_raw = [(workspace / r).resolve() for r in class_config.src_roots]

    parser_name = class_config.runtime.parser if class_config is not None else "legacy"
    try:
        frontend = resolve_java_frontend(parser_name)
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc

    by_fqcn: dict = {}
    by_simple: dict = {}
    for src_root in src_roots_raw:
        if not src_root.exists():
            print(f"[WARN] src_root does not exist, skipping: {src_root}")
            continue
        if parser_name == "legacy":
            root_fqcn, root_simple = index_workspace_types(workspace, src_root)
        else:
            root_fqcn, root_simple = frontend.class_indexer(workspace, src_root)
        by_fqcn.update(root_fqcn)
        for key, types in root_simple.items():
            by_simple.setdefault(key, []).extend(types)

    if not by_fqcn:
        raise RuntimeError(f"No Java types found under {src_roots_raw}")

    roots: list[JavaTypeInfo] = []
    depth = args.depth
    output_target = args.update_target_puml
    method_scope = "public"
    member_scope = "none"

    if class_config is not None:
        depth = class_config.depth
        output_target = class_config.output or output_target
        method_scope = class_config.method_scope
        member_scope = class_config.member_scope

        included_roots = resolve_roots_from_rules(rules=class_config.include, workspace=workspace, by_fqcn=by_fqcn)
        excluded_roots = resolve_roots_from_rules(rules=class_config.exclude, workspace=workspace, by_fqcn=by_fqcn)
        root_fqcns = sorted(included_roots - excluded_roots)
        roots = [by_fqcn[fqcn] for fqcn in root_fqcns]

        if not roots:
            print("[WARN] include/exclude resolved no root types; matched section updated")
            return 0
    else:
        if not args.input:
            raise ValueError("Either --config or --input is required")
        files = resolve_input_files(args.input, workspace)
        for path in files:
            root = determine_root_for_file(path, by_fqcn)
            if root:
                roots.append(root)

    if not roots:
        raise RuntimeError("No root Java types resolved")

    reverse_index = build_reverse_index(by_fqcn, by_simple)
    included, levels = merge_expansions(roots, depth, by_fqcn, by_simple, reverse_index)
    if class_config is not None:
        excluded_after_depth = resolve_roots_from_rules(
            rules=class_config.exclude,
            workspace=workspace,
            by_fqcn=by_fqcn,
        )
        included = {fqcn for fqcn in included if fqcn not in excluded_after_depth}
        levels = {fqcn: level for fqcn, level in levels.items() if fqcn in included}
        # Write all depth-expanded included types to matched (not just roots),
        # so the yaml reflects every class that actually appears in the diagram.
        if config_path is not None:
            matched = sorted(
                by_fqcn[fqcn].relpath
                for fqcn in included
                if fqcn in by_fqcn
            )
            write_matched_section(config_path, matched)

    ordered = topo_parent_first(included, by_fqcn, by_simple)
    edges = build_edges(included, by_fqcn, by_simple)

    if class_config is not None and class_config.observability.emit_summary:
        print(
            f"[OK] parser={class_config.runtime.parser} roots={len(roots)} included={len(included)} edges={len(edges)} depth={depth}"
        )

    if output_target:
        target = Path(output_target)
        if not target.is_absolute():
            target = (workspace / target).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)

        diagram_name = f"{target.stem}_Depth{depth}"
        if target.exists():
            for line in target.read_text(encoding="utf-8", errors="ignore").splitlines():
                match = re.match(r"^\s*@startuml\s+(.+?)\s*$", line)
                if match:
                    diagram_name = match.group(1)
                    break

        puml = build_puml(
            roots=roots,
            ordered=ordered,
            edges=edges,
            levels=levels,
            depth=depth,
            method_scope=method_scope,
            member_scope=member_scope,
            diagram_name=diagram_name,
        )
        puml_with_header = prepend_plantuml_header(puml, header_text)
        if config_path is not None:
            puml_with_header = insert_legend_block(puml_with_header, config_path, workspace)
        target.write_text(puml_with_header, encoding="utf-8")
        print(f"[OK] Updated {target}")
        return 0

    output_dir = (workspace / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    for root in roots:
        one_included, one_levels = expand_types_by_depth(root, depth, by_fqcn, by_simple)
        one_ordered = topo_parent_first(one_included, by_fqcn, by_simple)
        one_edges = build_edges(one_included, by_fqcn, by_simple)

        puml = build_puml(
            roots=[root],
            ordered=one_ordered,
            edges=one_edges,
            levels=one_levels,
            depth=depth,
            method_scope=method_scope,
            member_scope=member_scope,
            diagram_name=f"{root.name}_Depth{depth}",
        )
        puml_with_header = prepend_plantuml_header(puml, header_text)
        if config_path is not None:
            puml_with_header = insert_legend_block(puml_with_header, config_path, workspace)
        target = output_dir / f"{root.name}.puml"
        target.write_text(puml_with_header, encoding="utf-8")
        print(f"[OK] Generated {target}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
