#!/usr/bin/env python3
"""YAML config loader for umlgen class/sequence diagram workflows.

The contract is intentionally simple:
- include/exclude are plain string rule lists
- optional import files can contribute include/exclude rules
- class supports method_scope/member_scope
- both class/sequence keep src_roots (multi-path) and matched metadata
"""

from __future__ import annotations

from dataclasses import dataclass, field
import importlib
from pathlib import Path
import re
from typing import Any


class ConfigError(ValueError):
    """Raised when a umlgen yaml config is invalid."""


@dataclass(frozen=True)
class RuntimeConfig:
    """Normalized runtime config shared by class/sequence diagrams."""

    language: str = "java"
    parser: str = "legacy"
    strict: bool = False
    stable_sort_enabled: bool = False
    stable_sort_strategy: str = "by_name"
    parser_lock_file: str | None = None


@dataclass(frozen=True)
class EvidenceConfig:
    """Normalized evidence emission settings."""

    mode: str = "basic"
    include_caller: bool = False
    include_callee: bool = False
    include_source_line: bool = False


@dataclass(frozen=True)
class ObservabilityConfig:
    """Normalized observability switches."""

    emit_summary: bool = False


@dataclass(frozen=True)
class OutputConfig:
    """Normalized output settings."""

    path: str | None = None
    format: str = "plantuml"


@dataclass(frozen=True)
class ClassConfig:
    """Normalized class-diagram config."""

    depth: int
    output: str | None
    src_roots: tuple[str, ...]
    include: tuple[str, ...]
    exclude: tuple[str, ...]
    method_scope: str = "public"
    member_scope: str = "none"
    matched: tuple[str, ...] = ()
    imports: tuple[str, ...] = ()
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    evidence: EvidenceConfig = field(default_factory=EvidenceConfig)
    observability: ObservabilityConfig = field(default_factory=ObservabilityConfig)
    output_config: OutputConfig = field(default_factory=OutputConfig)


@dataclass(frozen=True)
class SequenceConfig:
    """Normalized sequence-diagram config."""

    depth: int
    output: str | None
    src_roots: tuple[str, ...]
    include: tuple[str, ...]
    exclude: tuple[str, ...]
    defined_hierarchy_paths: tuple[tuple[str, ...], ...] = ()
    matched: tuple[str, ...] = ()
    imports: tuple[str, ...] = ()
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    evidence: EvidenceConfig = field(default_factory=EvidenceConfig)
    observability: ObservabilityConfig = field(default_factory=ObservabilityConfig)
    output_config: OutputConfig = field(default_factory=OutputConfig)


@dataclass(frozen=True)
class DiagramConfig:
    """Union-like top-level diagram config."""

    diagram_type: str
    class_config: ClassConfig | None = None
    sequence_config: SequenceConfig | None = None
    version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


def _require_mapping(node: Any, path: str) -> dict[str, Any]:
    if not isinstance(node, dict):
        raise ConfigError(f"{path} must be a mapping")
    return node


def _optional_int(node: Any, path: str, default: int) -> int:
    if node is None:
        return default
    if not isinstance(node, int):
        raise ConfigError(f"{path} must be an integer")
    return node


def _optional_bool(node: Any, path: str, default: bool) -> bool:
    if node is None:
        return default
    if not isinstance(node, bool):
        raise ConfigError(f"{path} must be a boolean")
    return node


def _optional_str(node: Any, path: str, default: str | None = None) -> str | None:
    if node is None:
        return default
    if not isinstance(node, str):
        raise ConfigError(f"{path} must be a string")
    value = node.strip()
    return value if value else default


def _optional_path_str(node: Any, path: str, default: str | None = None) -> str | None:
    if node is None:
        return default
    if isinstance(node, str):
        return _optional_str(node, path, default)
    if isinstance(node, list):
        if len(node) != 1:
            raise ConfigError(f"{path} list form must contain exactly one string")
        item = node[0]
        if not isinstance(item, str):
            raise ConfigError(f"{path}[0] must be a string")
        value = item.strip()
        return value if value else default
    raise ConfigError(f"{path} must be a string or single-item list")


def _normalize_src_roots(node: Any, path: str, default: str = "src/main/java") -> tuple[str, ...]:
    """Accept a single string or a list of strings for src_root/src_roots."""
    if node is None:
        return (default,)
    if isinstance(node, str):
        value = node.strip()
        return (value,) if value else (default,)
    if isinstance(node, list):
        result: list[str] = []
        for index, item in enumerate(node):
            if not isinstance(item, str):
                raise ConfigError(f"{path}[{index}] must be a string")
            text = item.strip()
            if text:
                result.append(text)
        return tuple(result) if result else (default,)
    raise ConfigError(f"{path} must be a string or list of strings")


def _normalize_rule_list(raw: Any, path: str) -> tuple[str, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ConfigError(f"{path} must be a list")

    values: list[str] = []
    for index, item in enumerate(raw):
        if not isinstance(item, str):
            raise ConfigError(f"{path}[{index}] must be a string")
        text = item.strip()
        if text:
            values.append(text)
    return tuple(values)


def _normalize_imports(raw: Any, path: str) -> tuple[str, ...]:
    if raw is None:
        return ()
    if isinstance(raw, str):
        text = raw.strip()
        return (text,) if text else ()
    if isinstance(raw, list):
        values: list[str] = []
        for index, item in enumerate(raw):
            if not isinstance(item, str):
                raise ConfigError(f"{path}[{index}] must be a string")
            text = item.strip()
            if text:
                values.append(text)
        return tuple(values)
    raise ConfigError(f"{path} must be a string or list")


def _normalize_hierarchy_name(raw: Any, path: str) -> str:
    if not isinstance(raw, str):
        raise ConfigError(f"{path} must be a string")
    text = raw.strip()
    if not text:
        raise ConfigError(f"{path} must not be empty")
    return text


def _first_chain_from_hierarchy_node(raw: Any, path: str) -> tuple[str, ...]:
    """Extract one preferred hierarchy chain from a node.

    Rules:
    - Dict node: choose first key (as parent) and recurse into value.
    - Nested list node: first item is parent, second item is preferred child.
    - Sibling list node: choose first item (first child wins).
    - String node: leaf.
    """
    if isinstance(raw, str):
        return (_normalize_hierarchy_name(raw, path),)

    if isinstance(raw, list):
        if not raw:
            return ()

        if all(isinstance(item, str) for item in raw):
            return tuple(_normalize_hierarchy_name(item, f"{path}[{index}]") for index, item in enumerate(raw))

        first_item = raw[0]
        if isinstance(first_item, str):
            parent = _normalize_hierarchy_name(first_item, f"{path}[0]")
            if len(raw) == 1:
                return (parent,)
            child_chain = _first_chain_from_hierarchy_node(raw[1], f"{path}[1]")
            if not child_chain:
                return (parent,)
            return (parent,) + child_chain

        return _first_chain_from_hierarchy_node(raw[0], f"{path}[0]")

    if isinstance(raw, dict):
        if not raw:
            return ()
        first_key = next(iter(raw.keys()))
        parent = _normalize_hierarchy_name(first_key, f"{path}.<key>")
        child_chain = _first_chain_from_hierarchy_node(raw[first_key], f"{path}.{parent}")
        if not child_chain:
            return (parent,)
        return (parent,) + child_chain

    raise ConfigError(f"{path} must be a string, list, or mapping")


def _normalize_defined_hierarchy_paths(raw: Any, path: str) -> tuple[tuple[str, ...], ...]:
    """Normalize defined_hierarchy to ordered root->leaf chains.

    This keeps user ordering and applies the first-child-wins rule.
    """
    if raw is None:
        return ()

    entries: list[tuple[str, ...]] = []
    if isinstance(raw, list):
        for index, item in enumerate(raw):
            chain = _first_chain_from_hierarchy_node(item, f"{path}[{index}]")
            if chain:
                entries.append(chain)
        return tuple(entries)

    chain = _first_chain_from_hierarchy_node(raw, path)
    return (chain,) if chain else ()


def _parse_defined_hierarchy_paths_from_raw_text(raw_yaml: str) -> tuple[tuple[str, ...], ...]:
    """Parse defined_hierarchy from YAML text block notation used by umlgen configs.

    Supported notation:
    defined_hierarchy:
      - Parent
        - Child
          - GrandChild
      - AnotherParent
        - Child

    This parser intentionally applies first-child-wins semantics for sibling
    entries at the same depth under the same parent.
    """
    lines = raw_yaml.splitlines()

    section_start = None
    section_indent = 0
    for idx, line in enumerate(lines):
        match = re.match(r"^(?P<indent>\s*)defined_hierarchy:\s*$", line)
        if match:
            section_start = idx + 1
            section_indent = len(match.group("indent"))
            break

    if section_start is None:
        return ()

    entries: list[tuple[str, ...]] = []
    current_chain: list[str] = []
    seen_at_depth: set[tuple[str, int]] = set()
    base_indent: int | None = None

    for line in lines[section_start:]:
        if not line.strip():
            continue

        current_indent = len(line) - len(line.lstrip(" "))
        if current_indent <= section_indent and re.match(r"^\s*[^-\s][^:]*:\s*.*$", line):
            break

        bullet = re.match(r"^(?P<indent>\s*)-\s+(?P<name>.+?)\s*$", line)
        if not bullet:
            continue

        name = bullet.group("name").strip()
        if not name:
            continue

        indent = len(bullet.group("indent"))
        if base_indent is None:
            base_indent = indent

        # Only process entries that are under defined_hierarchy indentation.
        if indent < base_indent:
            continue

        depth = max(0, (indent - base_indent) // 2)

        if depth == 0:
            if current_chain:
                entries.append(tuple(current_chain))
            current_chain = [name]
            seen_at_depth = set()
            continue

        if not current_chain:
            continue

        if depth > len(current_chain):
            depth = len(current_chain)

        parent_path = tuple(current_chain[:depth])
        sibling_key = ("/".join(parent_path), depth)
        if sibling_key in seen_at_depth:
            continue

        current_chain = current_chain[:depth]
        current_chain.append(name)
        seen_at_depth.add(sibling_key)

    if current_chain:
        entries.append(tuple(current_chain))

    return tuple(entry for entry in entries if entry)


def _normalize_runtime(node: Any) -> RuntimeConfig:
    mapping = _require_mapping(node or {}, "config.runtime")
    language = _optional_str(mapping.get("language"), "config.runtime.language", "java") or "java"
    if language not in {"java", "python", "typescript", "javascript"}:
        raise ConfigError("config.runtime.language must be java, python, typescript, or javascript")

    parser = _optional_str(mapping.get("parser"), "config.runtime.parser", "legacy") or "legacy"
    if parser not in {"legacy", "tree-sitter", "ast", "spoon", "ts-morph"}:
        raise ConfigError("config.runtime.parser must be legacy, tree-sitter, ast, spoon, or ts-morph")

    stable_sort_node = _require_mapping(mapping.get("stable_sort", {}), "config.runtime.stable_sort")
    stable_sort_enabled = _optional_bool(
        stable_sort_node.get("enabled"),
        "config.runtime.stable_sort.enabled",
        False,
    )
    stable_sort_strategy = _optional_str(
        stable_sort_node.get("strategy"),
        "config.runtime.stable_sort.strategy",
        "by_name",
    ) or "by_name"

    return RuntimeConfig(
        language=language,
        parser=parser,
        strict=_optional_bool(mapping.get("strict"), "config.runtime.strict", False),
        stable_sort_enabled=stable_sort_enabled,
        stable_sort_strategy=stable_sort_strategy,
        parser_lock_file=_optional_path_str(
            mapping.get("parser_lock_file"),
            "config.runtime.parser_lock_file",
        ),
    )


def _normalize_evidence(node: Any) -> EvidenceConfig:
    mapping = _require_mapping(node or {}, "config.evidence")
    mode = _optional_str(mapping.get("mode"), "config.evidence.mode", "basic") or "basic"
    if mode not in {"off", "basic", "full"}:
        raise ConfigError("config.evidence.mode must be off, basic, or full")
    return EvidenceConfig(
        mode=mode,
        include_caller=_optional_bool(mapping.get("include_caller"), "config.evidence.include_caller", False),
        include_callee=_optional_bool(mapping.get("include_callee"), "config.evidence.include_callee", False),
        include_source_line=_optional_bool(
            mapping.get("include_source_line"),
            "config.evidence.include_source_line",
            False,
        ),
    )


def _normalize_observability(node: Any) -> ObservabilityConfig:
    mapping = _require_mapping(node or {}, "config.observability")
    return ObservabilityConfig(
        emit_summary=_optional_bool(
            mapping.get("emit_summary"),
            "config.observability.emit_summary",
            False,
        )
    )


def _normalize_output(node: Any) -> OutputConfig:
    if node is None:
        return OutputConfig()
    if isinstance(node, str):
        return OutputConfig(path=_optional_str(node, "config.output"))

    mapping = _require_mapping(node, "config.output")
    output_format = _optional_str(mapping.get("format"), "config.output.format", "plantuml") or "plantuml"
    return OutputConfig(
        path=_optional_path_str(mapping.get("path"), "config.output.path"),
        format=output_format,
    )


def _load_yaml(yaml_module: Any, path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml_module.safe_load(handle)
    return _require_mapping(loaded or {}, str(path))


def _merge_imported_rules(
    *,
    yaml_module: Any,
    config_dir: Path,
    import_paths: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    include_rules: list[str] = []
    exclude_rules: list[str] = []

    for raw_path in import_paths:
        resolved = Path(raw_path)
        if not resolved.is_absolute():
            local_candidate = (config_dir / resolved).resolve()
            workspace_candidate = (config_dir.parent / resolved).resolve()
            if local_candidate.exists():
                resolved = local_candidate
            elif workspace_candidate.exists():
                resolved = workspace_candidate
            else:
                resolved = local_candidate

        imported = _load_yaml(yaml_module, resolved)
        include_rules.extend(_normalize_rule_list(imported.get("include"), f"{resolved}:include"))
        exclude_rules.extend(_normalize_rule_list(imported.get("exclude"), f"{resolved}:exclude"))

    return tuple(include_rules), tuple(exclude_rules)


def _normalize_class_config(node: dict[str, Any], yaml_module: Any, config_path: Path) -> ClassConfig:
    depth = _optional_int(node.get("depth"), "config.depth", 2)
    if depth < 0:
        raise ConfigError("config.depth must be >= 0")

    method_scope = _optional_str(node.get("method_scope"), "config.method_scope", "public") or "public"
    member_scope = _optional_str(node.get("member_scope"), "config.member_scope", "none") or "none"
    if method_scope not in {"public", "all"}:
        raise ConfigError("config.method_scope must be 'public' or 'all'")
    if member_scope not in {"none", "all"}:
        raise ConfigError("config.member_scope must be 'none' or 'all'")

    imports = _normalize_imports(node.get("import"), "config.import")
    imported_include, imported_exclude = _merge_imported_rules(
        yaml_module=yaml_module,
        config_dir=config_path.parent,
        import_paths=imports,
    )

    include = imported_include + _normalize_rule_list(node.get("include"), "config.include")
    exclude = imported_exclude + _normalize_rule_list(node.get("exclude"), "config.exclude")
    runtime = _normalize_runtime(node.get("runtime"))
    evidence = _normalize_evidence(node.get("evidence"))
    observability = _normalize_observability(node.get("observability"))
    output_config = _normalize_output(node.get("output"))

    return ClassConfig(
        depth=depth,
        output=output_config.path,
        src_roots=_normalize_src_roots(node.get("src_root"), "config.src_root"),
        include=include,
        exclude=exclude,
        method_scope=method_scope,
        member_scope=member_scope,
        matched=_normalize_rule_list(node.get("matched"), "config.matched"),
        imports=imports,
        runtime=runtime,
        evidence=evidence,
        observability=observability,
        output_config=output_config,
    )


def _normalize_sequence_config(node: dict[str, Any], yaml_module: Any, config_path: Path) -> SequenceConfig:
    depth = _optional_int(node.get("depth"), "config.depth", 5)
    if depth < 0:
        raise ConfigError("config.depth must be >= 0")

    imports = _normalize_imports(node.get("import"), "config.import")
    imported_include, imported_exclude = _merge_imported_rules(
        yaml_module=yaml_module,
        config_dir=config_path.parent,
        import_paths=imports,
    )

    include = imported_include + _normalize_rule_list(node.get("include"), "config.include")
    exclude = imported_exclude + _normalize_rule_list(node.get("exclude"), "config.exclude")
    runtime = _normalize_runtime(node.get("runtime"))
    evidence = _normalize_evidence(node.get("evidence"))
    observability = _normalize_observability(node.get("observability"))
    output_config = _normalize_output(node.get("output"))

    defined_paths_from_yaml = _normalize_defined_hierarchy_paths(
        node.get("defined_hierarchy"),
        "config.defined_hierarchy",
    )
    defined_paths_from_text = _parse_defined_hierarchy_paths_from_raw_text(
        config_path.read_text(encoding="utf-8")
    )

    return SequenceConfig(
        depth=depth,
        output=output_config.path,
        src_roots=_normalize_src_roots(node.get("src_root"), "config.src_root"),
        include=include,
        exclude=exclude,
        defined_hierarchy_paths=defined_paths_from_text or defined_paths_from_yaml,
        matched=_normalize_rule_list(node.get("matched"), "config.matched"),
        imports=imports,
        runtime=runtime,
        evidence=evidence,
        observability=observability,
        output_config=output_config,
    )


def load_diagram_config(config_path: Path) -> DiagramConfig:
    """Load and normalize a umlgen yaml file from disk."""

    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    try:
        yaml_module = importlib.import_module("yaml")
    except Exception as exc:  # pragma: no cover - runtime environment specific
        raise ConfigError(
            "PyYAML is required for --config mode. Install it with: pip install pyyaml"
        ) from exc

    root = _load_yaml(yaml_module, config_path)
    version = _optional_int(root.get("version"), "config.version", 1)

    diagram_node = _require_mapping(root.get("diagram", {}), "config.diagram")
    diagram_type = _optional_str(diagram_node.get("type"), "config.diagram.type", "class") or "class"
    if diagram_type not in {"class", "sequence"}:
        raise ConfigError("config.diagram.type must be 'class' or 'sequence'")
    metadata = _require_mapping(diagram_node.get("metadata", {}), "config.diagram.metadata")

    if diagram_type == "class":
        class_config = _normalize_class_config(root, yaml_module, config_path)
        return DiagramConfig(
            diagram_type="class",
            class_config=class_config,
            sequence_config=None,
            version=version,
            metadata=metadata,
        )

    sequence_config = _normalize_sequence_config(root, yaml_module, config_path)
    return DiagramConfig(
        diagram_type="sequence",
        class_config=None,
        sequence_config=sequence_config,
        version=version,
        metadata=metadata,
    )
