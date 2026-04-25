#!/usr/bin/env python3
"""Convert UMLC (XML) class diagram into PlantUML.

Default output is readability-oriented and uses short class labels.
"""

from __future__ import annotations

import argparse
import os
import re
import xml.etree.ElementTree as ET
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

from umlgen_pkg.umlgen_file_header import prepend_plantuml_header, read_mark_file

CTRL_KEYWORDS = {
    "if",
    "for",
    "while",
    "switch",
    "catch",
    "new",
    "return",
    "throw",
    "do",
    "try",
    "synchronized",
}

FIELD_SKIP_TOKENS = {
    "public",
    "protected",
    "private",
    "static",
    "final",
    "volatile",
    "transient",
    "default",
}

DEFAULT_EXCLUDE_REGEX = [r"(?i).*launchdarkly.*"]


@dataclass
class Classifier:
    id: str
    kind: str
    name: str
    file: str
    binary: bool
    relpath: str | None
    synthetic_nested: bool = False
    members: list[tuple[str, str, int]] | None = None
    decl_line: int | None = None


def clean_line(text: str) -> str:
    return text.strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert UMLC to PlantUML")
    parser.add_argument("--input", help="Path to input .umlc XML")
    parser.add_argument("--output", help="Path to output .puml")
    parser.add_argument(
        "--batch-input-dir",
        help="Recursively convert all .umlc files in this directory",
    )
    parser.add_argument(
        "--batch-output-dir",
        default="docs",
        help="Output folder for batch mode (default: docs)",
    )
    parser.add_argument(
        "--batch-pattern",
        default="*.umlc",
        help="Glob pattern for batch mode (default: *.umlc)",
    )
    parser.add_argument(
        "--batch-prefix",
        default="umlc",
        help="Filename prefix in batch mode (default: umlc)",
    )
    parser.add_argument(
        "--date",
        default=None,
        help="Optional date used in batch output names (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--workspace",
        default=os.getcwd(),
        help="Workspace root used to resolve source file links (default: cwd)",
    )
    parser.add_argument(
        "--full-names",
        action="store_true",
        help="Use fully-qualified class names in PlantUML labels",
    )
    parser.add_argument(
        "--exclude-regex",
        action="append",
        default=[],
        help=(
            "Exclude classes by regex on fully-qualified name. "
            "Can be provided multiple times. "
            "Default excludes LaunchDarkly classes."
        ),
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if args.batch_input_dir:
        if args.input or args.output:
            raise ValueError("Do not combine --batch-input-dir with --input/--output")
        return

    if not args.input or not args.output:
        raise ValueError("Single-file mode requires both --input and --output")


def normalize_stem(text: str) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return value or "diagram"


def compile_exclude_patterns(extra: list[str]) -> list[re.Pattern[str]]:
    patterns: list[re.Pattern[str]] = []
    for pattern in DEFAULT_EXCLUDE_REGEX + extra:
        patterns.append(re.compile(pattern))
    return patterns


def is_excluded(name: str, patterns: list[re.Pattern[str]]) -> bool:
    return any(p.search(name) for p in patterns)


def resolve_relpath(workspace: str, file_path: str, project: str = "") -> str | None:
    """Resolve a file path from the XML 'file' attribute to a workspace-relative path.

    The XML 'file' attribute typically contains a project-prefixed absolute path
    like ``/my-project/src/main/java/...``.  The ``project`` argument (taken from
    the XML 'project' attribute) is used to strip that prefix dynamically instead
    of relying on a hardcoded project name.
    """
    relpath = file_path
    if project:
        marker = f"/{project}/"
        if marker in file_path:
            relpath = file_path.split(marker, 1)[1]
    if relpath == file_path and file_path.startswith(workspace + "/"):
        relpath = file_path[len(workspace) + 1:]

    if not relpath or relpath == file_path:
        return None

    full = os.path.join(workspace, relpath)
    return relpath if os.path.exists(full) else None


def load_classifiers(
    root: ET.Element,
    workspace: str,
    exclude_patterns: list[re.Pattern[str]],
) -> OrderedDict[str, Classifier]:
    classifiers: OrderedDict[str, Classifier] = OrderedDict()
    for tag, kind in (("class", "class"), ("interface", "interface"), ("enumeration", "enum")):
        for node in root.findall(tag):
            cid = node.attrib["id"]
            name = node.attrib.get("name", "")
            if is_excluded(name, exclude_patterns):
                continue
            file_path = node.attrib.get("file", "")
            project = node.attrib.get("project", "")
            classifiers[cid] = Classifier(
                id=cid,
                kind=kind,
                name=name,
                file=file_path,
                binary=node.attrib.get("binary", "false") == "true",
                relpath=resolve_relpath(workspace, file_path, project),
            )
    return classifiers


def get_type_block(lines: list[str], fq_name: str) -> tuple[int, int]:
    parts = fq_name.split(".")
    simple = parts[-1]
    search = [simple]
    if len(parts) >= 2 and parts[-2][:1].isupper():
        search = [parts[-2], simple]

    lo, hi = 1, len(lines)
    for name in search:
        idx = None
        for i in range(lo, hi + 1):
            text = clean_line(lines[i - 1])
            if text.startswith("//") or text.startswith("*") or text.startswith("/*"):
                continue
            if re.search(rf"\b(class|interface|enum|record)\s+{re.escape(name)}\b", text):
                idx = i
                break

        if idx is None:
            return 1, len(lines)

        depth = 0
        seen_brace = False
        end = hi
        for j in range(idx, hi + 1):
            for ch in lines[j - 1]:
                if ch == "{":
                    depth += 1
                    seen_brace = True
                elif ch == "}" and seen_brace:
                    depth -= 1
            if seen_brace and depth == 0:
                end = j
                break

        lo, hi = idx, end

    return lo, hi


def add_nested_types(workspace: str, classifiers: OrderedDict[str, Classifier]) -> None:
    if not classifiers:
        return

    existing = {c.name for c in classifiers.values()}
    max_id = max(int(k) for k in classifiers)

    for c in list(classifiers.values()):
        if not c.relpath or c.binary:
            continue

        with open(os.path.join(workspace, c.relpath), encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()

        lo, hi = get_type_block(lines, c.name)
        depth = 0
        seen_brace = False

        for ln in range(lo, hi + 1):
            text = clean_line(lines[ln - 1])
            if depth == 1 and text and not text.startswith(("//", "*", "/*")):
                match = re.match(
                    r"(?:public|protected|private)?\s*(?:static\s+)?(?:final\s+)?"
                    r"(class|interface|enum)\s+([A-Za-z_$][\w$]*)\b",
                    text,
                )
                if match:
                    nested_name = f"{c.name}.{match.group(2)}"
                    if nested_name not in existing:
                        max_id += 1
                        kind = match.group(1)
                        classifiers[str(max_id)] = Classifier(
                            id=str(max_id),
                            kind="enum" if kind == "enum" else kind,
                            name=nested_name,
                            file=c.file,
                            binary=False,
                            relpath=c.relpath,
                            synthetic_nested=True,
                        )
                        existing.add(nested_name)

            for ch in lines[ln - 1]:
                if ch == "{":
                    depth += 1
                    seen_brace = True
                elif ch == "}" and seen_brace:
                    depth -= 1


def extract_members(workspace: str, c: Classifier) -> tuple[list[tuple[str, str, int]], int | None]:
    if not c.relpath:
        return [], None

    with open(os.path.join(workspace, c.relpath), encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()

    lo, hi = get_type_block(lines, c.name)
    members: list[tuple[str, str, int]] = []

    depth = 0
    seen_brace = False
    for ln in range(lo, hi + 1):
        raw = lines[ln - 1]
        text = clean_line(raw)

        if (
            depth == 1
            and text
            and not text.startswith(("//", "*", "/*", "@"))
            and not re.search(r"\b(class|interface|enum|record)\b", text)
        ):
            if c.kind == "interface":
                # Keep interface output stable and avoid false positives from parameter/throws lines.
                if "(" in text:
                    match = re.search(r"([A-Za-z_$][\w$]*)\s*\(", text)
                    if match:
                        name = match.group(1)
                        if name not in CTRL_KEYWORDS:
                            members.append(("method", f"{name}()", ln))
            else:
                if text.startswith("public ") or text.startswith("protected "):
                    if "(" in text:
                        # method (single-line or start of multi-line signature)
                        match = re.search(r"([A-Za-z_$][\w$]*)\s*\(", text)
                        if match:
                            name = match.group(1)
                            if name not in CTRL_KEYWORDS:
                                members.append(("method", f"{name}()", ln))
                    elif ";" in text or "=" in text or "," in text:
                        # skip constants: public static final ...
                        toks = set(re.split(r"\s+", text))
                        if "static" in toks and "final" in toks:
                            pass
                        else:
                            striped = re.sub(r"\s*=.*", "", text)
                            tokens = [t for t in re.split(r"\s+", striped) if t and t not in FIELD_SKIP_TOKENS]
                            if tokens:
                                name = tokens[-1].rstrip(";,")
                                if re.match(r"^[A-Za-z_$][\w$]*$", name):
                                    members.append(("field", name, ln))

        for ch in raw:
            if ch == "{":
                depth += 1
                seen_brace = True
            elif ch == "}" and seen_brace:
                depth -= 1

    deduped: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for item in members:
        if item not in seen:
            deduped.append(item)
            seen.add(item)

    return deduped, lo


def parse_relationships(root: ET.Element) -> list[dict]:
    relationships: list[dict] = []

    for rel_type in ("generalization", "realization", "association", "nesting"):
        for rel in root.findall(rel_type):
            if rel_type == "association":
                se = rel.find("end[@type='SOURCE']")
                te = rel.find("end[@type='TARGET']")

                def parse_end(end: ET.Element | None) -> dict:
                    if end is None:
                        return {}
                    out: dict[str, str] = {"refId": end.attrib.get("refId", "")}
                    attr = end.find("attribute")
                    mult = end.find("multiplicity")
                    if attr is not None:
                        out["name"] = attr.attrib.get("name", "")
                    if mult is not None:
                        mn = mult.attrib.get("minimum")
                        mx = mult.attrib.get("maximum")
                        mx = "*" if mx == "2147483647" else mx
                        out["mult"] = mn if mn == mx else f"{mn}..{mx}"
                    return out

                relationships.append(
                    {
                        "type": "association",
                        "source_end": parse_end(se),
                        "target_end": parse_end(te),
                    }
                )
            else:
                source = rel.find("end[@type='SOURCE']").attrib.get("refId")
                target = rel.find("end[@type='TARGET']").attrib.get("refId")
                relationships.append({"type": rel_type, "source": source, "target": target})

    return relationships


def choose_display_names(classifiers: OrderedDict[str, Classifier], use_full_names: bool) -> dict[str, str]:
    if use_full_names:
        return {cid: c.name for cid, c in classifiers.items()}

    display: dict[str, str] = {}
    unresolved = {cid: c.name.split(".") for cid, c in classifiers.items()}

    for depth in range(1, 8):
        buckets: dict[str, list[str]] = {}
        for cid, parts in unresolved.items():
            label = ".".join(parts[-depth:]) if depth <= len(parts) else ".".join(parts)
            buckets.setdefault(label, []).append(cid)

        progress = False
        for label, ids in buckets.items():
            if len(ids) == 1:
                cid = ids[0]
                if cid not in display:
                    display[cid] = label
                    progress = True

        if len(display) == len(classifiers):
            break

        unresolved = {cid: unresolved[cid] for cid in classifiers if cid not in display}
        if not progress and depth >= 6:
            break

    for cid, c in classifiers.items():
        display.setdefault(cid, c.name)

    return display


def build_plantuml(
    classifiers: OrderedDict[str, Classifier],
    relationships: list[dict],
    use_full_names: bool,
) -> str:
    display_names = choose_display_names(classifiers, use_full_names)

    lines = [
        "@startuml",
        "hide empty members",
        "skinparam classAttributeIconSize 0",
        "top to bottom direction",
        "",
    ]

    for cid, c in classifiers.items():
        alias = f"C{cid}"
        label = display_names[cid]
        link = f" [[{c.relpath}:{c.decl_line}]]" if c.relpath and c.decl_line else ""

        lines.append(f'{c.kind} "{label}" as {alias}{link} {{')
        for _, member_name, line_no in c.members or []:
            if c.relpath:
                lines.append(f"  + [[{c.relpath}:{line_no} {member_name}]]")
            else:
                lines.append(f"  + {member_name}")
        lines.append("}")
        lines.append("")

    def exists(ref_id: str | None) -> bool:
        return bool(ref_id) and ref_id in classifiers

    def is_enum(ref_id: str | None) -> bool:
        if not exists(ref_id):
            return False
        return classifiers[ref_id].kind == "enum"

    for rel in relationships:
        rel_type = rel["type"]
        if rel_type in {"generalization", "realization", "nesting"}:
            s = rel["source"]
            t = rel["target"]
            if not exists(s) or not exists(t):
                continue
            if is_enum(s) or is_enum(t):
                continue
            if rel_type == "generalization":
                lines.append(f"C{s} --|> C{t}")
            elif rel_type == "realization":
                lines.append(f"C{s} ..|> C{t}")
            else:
                lines.append(f"C{s} +-- C{t} : nesting")
            continue

        se = rel["source_end"]
        te = rel["target_end"]
        s = se.get("refId")
        t = te.get("refId")
        if not exists(s) or not exists(t):
            continue
        if is_enum(s) or is_enum(t):
            continue

        left_mult = f' "{te.get("mult")}"' if te.get("mult") else ""
        right_mult = f' "{se.get("mult")}"' if se.get("mult") else ""
        labels: list[str] = []
        if se.get("name"):
            labels.append(se.get("name"))
        if te.get("name"):
            labels.append(te.get("name"))

        line = f"C{t}{left_mult} -->{right_mult} C{s}"
        if labels:
            line += " : " + "; ".join(labels)
        lines.append(line)

    lines.append("@enduml")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    validate_args(args)

    workspace = os.path.abspath(args.workspace)
    exclude_patterns = compile_exclude_patterns(args.exclude_regex)

    def convert_single(input_path: str, output_path: str) -> dict[str, int | str]:
        root = ET.parse(input_path).getroot()
        classifiers = load_classifiers(root, workspace, exclude_patterns)
        add_nested_types(workspace, classifiers)

        for c in classifiers.values():
            c.members, c.decl_line = extract_members(workspace, c)

        relationships = parse_relationships(root)
        text = build_plantuml(classifiers, relationships, use_full_names=args.full_names)
        header_text = read_mark_file(__file__)
        text_with_header = prepend_plantuml_header(text, header_text)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text_with_header)

        nested_count = sum(1 for c in classifiers.values() if c.synthetic_nested)
        return {
            "output": output_path,
            "classifiers": len(classifiers),
            "relationships": len(relationships),
            "nested_added": nested_count,
            "bytes": len(text),
        }

    if args.batch_input_dir:
        batch_input_dir = Path(args.batch_input_dir)
        batch_output_dir = Path(args.batch_output_dir)
        umlc_files = sorted(batch_input_dir.rglob(args.batch_pattern))
        if not umlc_files:
            print("done files=0")
            return 0

        converted = 0
        for umlc_file in umlc_files:
            stem = normalize_stem(umlc_file.stem)
            name_parts = [args.batch_prefix, stem]
            if args.date:
                name_parts.insert(0, args.date)
            output_name = "-".join(name_parts) + ".puml"
            output_path = str((batch_output_dir / output_name).resolve())
            stats = convert_single(str(umlc_file.resolve()), output_path)
            converted += 1
            print(
                "converted",
                f"input={umlc_file}",
                f"output={stats['output']}",
                f"classifiers={stats['classifiers']}",
                f"relationships={stats['relationships']}",
            )

        print("done", f"files={converted}")
        return 0

    input_path = os.path.abspath(args.input)
    output_path = os.path.abspath(args.output)
    stats = convert_single(input_path, output_path)
    print(
        "done",
        f"classifiers={stats['classifiers']}",
        f"relationships={stats['relationships']}",
        f"nested_added={stats['nested_added']}",
        f"bytes={stats['bytes']}",
        f"output={stats['output']}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
