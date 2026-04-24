#!/usr/bin/env python3
"""Convert legacy UMLS sequence XML into PlantUML sequence diagrams.

The output favors readability:
- participants show instance label plus short class name
- message labels keep method name and short argument types only
- participants and message labels link back to source files when resolvable
"""

from __future__ import annotations

import argparse
import html
import os
import re
import xml.etree.ElementTree as ET
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path

from umlgen_file_header import prepend_plantuml_header, read_mark_file


JAVA_TYPE_RE = re.compile(r"\b(?:[A-Za-z_$][\w$]*\.)+[A-Za-z_$][\w$]*\b")
METHOD_NAME_RE = re.compile(r"([A-Za-z_$][\w$]*)\s*\(")
CLASS_DECL_RE = re.compile(r"\b(class|interface|enum|record)\s+([A-Za-z_$][\w$]*)\b")
METHOD_DECL_TEMPLATE = (
    r"(?:public|protected|private|static|final|abstract|synchronized|default|native|strictfp)"
)


@dataclass
class DiagramObject:
    id: str
    name: str
    label: str
    file: str
    relpath: str | None
    short_name: str
    decl_line: int | None
    execution_ids: list[str] = field(default_factory=list)


@dataclass
class DiagramMessage:
    id: str
    operation: str | None
    asynchronous: bool
    source_execution_id: str
    target_execution_id: str
    source_object_id: str
    target_object_id: str
    label: str | None
    source_line: int | None
    caller_line: int | None


@dataclass
class FragmentOperand:
    id: str
    fragment_ids: list[str]


@dataclass
class CombinedFragment:
    id: str
    operator: str
    operands: list[FragmentOperand]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert UMLS to PlantUML sequence diagram")
    parser.add_argument("--input", help="Path to input .umls XML")
    parser.add_argument("--output", help="Path to output .puml")
    parser.add_argument(
        "--batch-input-dir",
        help="Recursively convert all .umls files in this directory",
    )
    parser.add_argument(
        "--batch-output-dir",
        default="docs",
        help="Output folder for batch mode (default: docs)",
    )
    parser.add_argument(
        "--batch-pattern",
        default="*.umls",
        help="Glob pattern for batch mode (default: *.umls)",
    )
    parser.add_argument(
        "--batch-prefix",
        default="umls",
        help="Filename prefix in batch mode (default: umls)",
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


def resolve_relpath(workspace: str, file_path: str) -> str | None:
    if not file_path:
        return None

    workspace_name = os.path.basename(workspace.rstrip(os.sep))
    marker = f"/{workspace_name}/"
    relpath = file_path

    if marker in file_path:
        relpath = file_path.split(marker, 1)[1]
    elif file_path.startswith(workspace + os.sep):
        relpath = file_path[len(workspace) + 1 :]
    else:
        relpath = file_path.lstrip("/")

    full_path = os.path.join(workspace, relpath)
    return relpath if os.path.exists(full_path) else None


def short_type_name(type_name: str) -> str:
    def repl(match: re.Match[str]) -> str:
        return match.group(0).split(".")[-1]

    return JAVA_TYPE_RE.sub(repl, type_name)


def split_top_level_arguments(argument_string: str) -> list[str]:
    if not argument_string.strip():
        return []

    args: list[str] = []
    current: list[str] = []
    depth = 0
    for char in argument_string:
        if char == "<":
            depth += 1
        elif char == ">" and depth > 0:
            depth -= 1
        elif char == "," and depth == 0:
            args.append("".join(current).strip())
            current = []
            continue
        current.append(char)

    if current:
        args.append("".join(current).strip())

    return args


def parse_operation(operation: str | None) -> tuple[str | None, str | None]:
    if not operation:
        return None, None

    decoded = html.unescape(operation)
    method_name, _, remainder = decoded.partition("(")
    method_name = method_name.strip()
    if not remainder:
        return decoded.strip(), method_name or None

    args_text, _, _return_type = remainder.partition(")")
    args = split_top_level_arguments(args_text)
    short_args = [short_type_name(arg).strip() for arg in args if arg.strip()]
    short_label = f"{method_name}({', '.join(short_args)})"
    return short_label, method_name or None


def sanitize_alias(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", value)
    if not cleaned:
        return "participant"
    if cleaned[0].isdigit():
        return f"P_{cleaned}"
    return cleaned


def read_lines(workspace: str, relpath: str | None) -> list[str]:
    if not relpath:
        return []
    full_path = os.path.join(workspace, relpath)
    with open(full_path, encoding="utf-8") as handle:
        return handle.read().splitlines()


def find_class_decl_line(lines: list[str], fqcn: str) -> int | None:
    if not lines:
        return None

    simple_name = fqcn.split(".")[-1]
    outer_name = None
    parts = fqcn.split(".")
    if len(parts) >= 2 and parts[-2][:1].isupper():
        outer_name = parts[-2]

    candidate_names = [simple_name]
    if outer_name:
        candidate_names.insert(0, outer_name)

    matched_lines: list[int] = []
    for target_name in candidate_names:
        for index, line in enumerate(lines, start=1):
            if CLASS_DECL_RE.search(line) and re.search(
                rf"\b(class|interface|enum|record)\s+{re.escape(target_name)}\b", line
            ):
                matched_lines.append(index)
                break

    return matched_lines[-1] if matched_lines else None


def is_probable_method_declaration(window: str, method_name: str) -> bool:
    if "." + method_name + "(" in window:
        return False

    signature_pattern = re.compile(
        rf"(?:{METHOD_DECL_TEMPLATE}|\s)+[\w<>,\[\].?@ ]+\b{re.escape(method_name)}\s*\(",
    )
    compact = " ".join(window.split())
    return bool(signature_pattern.search(compact))


def declaration_line_in_window(
    window_lines: list[str],
    method_name: str,
    start_line: int,
) -> int:
    """Return the real declaration line within a matched method window."""
    pattern = re.compile(rf"\b{re.escape(method_name)}\s*\(")
    for offset, line in enumerate(window_lines):
        if not pattern.search(line):
            continue
        if "." + method_name + "(" in line:
            continue
        return start_line + offset
    return start_line


def find_method_decl_line(lines: list[str], method_name: str) -> int | None:
    if not lines or not method_name:
        return None

    for index in range(len(lines)):
        raw = lines[index]
        stripped = raw.strip()
        if stripped.startswith(("//", "/*", "*")):
            continue

        window_lines = lines[index : index + 3]
        window = " ".join(line.strip() for line in window_lines)
        if f"{method_name}(" not in window:
            continue
        if is_probable_method_declaration(window, method_name):
            return declaration_line_in_window(window_lines, method_name, index + 1)

    return None


def find_call_line(lines: list[str], method_name: str) -> int | None:
    if not lines or not method_name:
        return None

    pattern = re.compile(rf"\b{re.escape(method_name)}\s*\(")
    for index, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith(("//", "/*", "*")):
            continue
        if pattern.search(line):
            return index
    return None


def load_objects(root: ET.Element, workspace: str) -> tuple[OrderedDict[str, DiagramObject], dict[str, str]]:
    objects: OrderedDict[str, DiagramObject] = OrderedDict()
    execution_to_object: dict[str, str] = {}

    for node in root.findall("object"):
        object_id = node.attrib["id"]
        fqcn = node.attrib.get("name", "")
        relpath = resolve_relpath(workspace, node.attrib.get("file", ""))
        short_name = fqcn.split(".")[-1] if fqcn else node.attrib.get("label", object_id)
        decl_line = find_class_decl_line(read_lines(workspace, relpath), fqcn)
        diagram_object = DiagramObject(
            id=object_id,
            name=fqcn,
            label=node.attrib.get("label", short_name),
            file=node.attrib.get("file", ""),
            relpath=relpath,
            short_name=short_name,
            decl_line=decl_line,
        )
        for execution in node.findall("execution"):
            execution_id = execution.attrib["id"]
            diagram_object.execution_ids.append(execution_id)
            execution_to_object[execution_id] = object_id
        objects[object_id] = diagram_object

    return objects, execution_to_object


def load_messages(
    root: ET.Element,
    workspace: str,
    objects: OrderedDict[str, DiagramObject],
    execution_to_object: dict[str, str],
) -> list[DiagramMessage]:
    object_lines = {obj.id: read_lines(workspace, obj.relpath) for obj in objects.values()}
    messages: list[DiagramMessage] = []

    for node in root.findall("message"):
        source_end = node.find("end[@type='SOURCE']")
        target_end = node.find("end[@type='TARGET']")
        if source_end is None or target_end is None:
            continue

        source_execution_id = source_end.attrib.get("refId", "")
        target_execution_id = target_end.attrib.get("refId", "")
        source_object_id = execution_to_object.get(source_execution_id)
        target_object_id = execution_to_object.get(target_execution_id)
        if not source_object_id or not target_object_id:
            continue

        label, method_name = parse_operation(node.attrib.get("operation"))
        if not label:
            continue
        target_lines = object_lines.get(target_object_id, [])
        source_lines = object_lines.get(source_object_id, [])
        source_line = find_method_decl_line(target_lines, method_name or "")
        caller_line = find_call_line(source_lines, method_name or "")

        messages.append(
            DiagramMessage(
                id=node.attrib["id"],
                operation=node.attrib.get("operation"),
                asynchronous=node.attrib.get("asynchronous", "false") == "true",
                source_execution_id=source_execution_id,
                target_execution_id=target_execution_id,
                source_object_id=source_object_id,
                target_object_id=target_object_id,
                label=label,
                source_line=source_line,
                caller_line=caller_line,
            )
        )

    messages.sort(key=lambda item: int(item.id))
    return messages


def load_combined_fragments(root: ET.Element) -> list[CombinedFragment]:
    fragments: list[CombinedFragment] = []
    for node in root.findall("combined-fragment"):
        operands: list[FragmentOperand] = []
        for operand in node.findall("interaction-operand"):
            operands.append(
                FragmentOperand(
                    id=operand.attrib["id"],
                    fragment_ids=[fragment.attrib.get("refId", "") for fragment in operand.findall("fragment")],
                )
            )
        fragments.append(
            CombinedFragment(
                id=node.attrib["id"],
                operator=node.attrib.get("interaction-operator", "group").lower(),
                operands=operands,
            )
        )
    return fragments


def participant_label(diagram_object: DiagramObject) -> str:
    if diagram_object.label and diagram_object.label != diagram_object.short_name:
        return f"{diagram_object.label}:\\n{diagram_object.short_name}"
    return diagram_object.short_name


def participant_link(diagram_object: DiagramObject) -> str:
    if diagram_object.relpath and diagram_object.decl_line:
        return f" [[{diagram_object.relpath}:{diagram_object.decl_line}]]"
    return ""


def message_evidence(message: DiagramMessage, source_object: DiagramObject, target_object: DiagramObject) -> str:
    chunks: list[str] = []

    if target_object.relpath and message.source_line:
        short_link = f"{Path(target_object.relpath).name}:{message.source_line}"
        chunks.append(f"callee:[[{target_object.relpath}:{message.source_line} {short_link}]]")

    if source_object.relpath and message.caller_line:
        short_link = f"{Path(source_object.relpath).name}:{message.caller_line}"
        chunks.append(f"caller:[[{source_object.relpath}:{message.caller_line} {short_link}]]")

    if not chunks:
        return ""
    return "\\n" + "\\n".join(chunks)


def build_fragment_events(
    fragments: list[CombinedFragment],
    messages: list[DiagramMessage],
) -> tuple[dict[int, list[str]], dict[int, list[str]]]:
    message_index = {message.id: idx for idx, message in enumerate(messages)}
    message_by_id = {message.id: message for message in messages}
    opens: dict[int, list[str]] = {}
    closes: dict[int, list[str]] = {}

    def method_name_from_label(label: str | None) -> str | None:
        if not label:
            return None
        method_name = label.split("(", 1)[0].strip()
        return method_name or None

    def summarize_fragment(fragment_ids: list[str]) -> str:
        method_names: list[str] = []
        for fragment_id in fragment_ids:
            message = message_by_id.get(fragment_id)
            method_name = method_name_from_label(message.label if message else None)
            if method_name and method_name not in method_names:
                method_names.append(method_name)
            if len(method_names) >= 2:
                break

        if not method_names:
            return "flow"
        if len(method_names) == 1:
            return method_names[0]
        return " / ".join(method_names)

    for fragment in fragments:
        operand_ranges: list[tuple[int, int]] = []
        for operand in fragment.operands:
            indices = [message_index[fragment_id] for fragment_id in operand.fragment_ids if fragment_id in message_index]
            if not indices:
                continue
            operand_ranges.append((min(indices), max(indices)))

        if not operand_ranges:
            continue

        overall_end = max(end for _, end in operand_ranges)
        operator = fragment.operator if fragment.operator in {"alt", "loop", "opt", "par", "break", "critical", "group"} else "group"
        if len(operand_ranges) == 1 and operator == "alt":
            operator = "group"

        sorted_operands = sorted(
            [
                (
                    min(
                        message_index[fragment_id]
                        for fragment_id in operand.fragment_ids
                        if fragment_id in message_index
                    ),
                    operand,
                )
                for operand in fragment.operands
                if any(fragment_id in message_index for fragment_id in operand.fragment_ids)
            ],
            key=lambda item: item[0],
        )

        for position, (start, operand) in enumerate(sorted_operands):
            summary = summarize_fragment(operand.fragment_ids)
            if position == 0:
                label = f"{operator} {summary}"
            elif operator == "alt":
                label = f"else {summary}"
            else:
                label = f"else operand {position + 1}"
            opens.setdefault(start, []).append(label)

        closes.setdefault(overall_end, []).append("end")

    return opens, closes


def build_plantuml(
    objects: OrderedDict[str, DiagramObject],
    messages: list[DiagramMessage],
    fragments: list[CombinedFragment],
) -> str:
    alias_map = {
        object_id: f"{sanitize_alias(diagram_object.label)}_{object_id}"
        for object_id, diagram_object in objects.items()
    }
    fragment_opens, fragment_closes = build_fragment_events(fragments, messages)

    lines = [
        "@startuml",
        "hide footbox",
        "skinparam ParticipantPadding 20",
        "skinparam BoxPadding 10",
        "autoactivate on",
        "",
    ]

    for object_id, diagram_object in objects.items():
        lines.append(
            f'participant "{participant_label(diagram_object)}" as {alias_map[object_id]}{participant_link(diagram_object)}'
        )

    lines.append("")

    for index, message in enumerate(messages):
        for open_line in fragment_opens.get(index, []):
            lines.append(open_line)

        source_alias = alias_map[message.source_object_id]
        target_alias = alias_map[message.target_object_id]
        arrow = "->>" if message.asynchronous else "->"
        message_text = ""
        if message.label:
            source_object = objects[message.source_object_id]
            target_object = objects[message.target_object_id]
            message_text = f" : {message.label}{message_evidence(message, source_object, target_object)}"
        lines.append(f"{source_alias} {arrow} {target_alias}{message_text}")

        for close_line in fragment_closes.get(index, []):
            lines.append(close_line)

    lines.append("@enduml")
    return "\n".join(lines) + "\n"


def convert_single(input_path: str, output_path: str, workspace: str) -> dict[str, int | str]:
    root = ET.parse(input_path).getroot()
    objects, execution_to_object = load_objects(root, workspace)
    messages = load_messages(root, workspace, objects, execution_to_object)
    fragments = load_combined_fragments(root)
    text = build_plantuml(objects, messages, fragments)
    header_text = read_mark_file(__file__)
    text_with_header = prepend_plantuml_header(text, header_text)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(text_with_header)

    return {
        "objects": len(objects),
        "messages": len(messages),
        "fragments": len(fragments),
        "output": output_path,
    }


def main() -> int:
    args = parse_args()
    validate_args(args)
    workspace = os.path.abspath(args.workspace)

    if args.batch_input_dir:
        input_dir = Path(args.batch_input_dir)
        output_dir = Path(args.batch_output_dir)
        umls_files = sorted(input_dir.rglob(args.batch_pattern))
        if not umls_files:
            print("done files=0")
            return 0

        converted = 0
        for umls_file in umls_files:
            stem = normalize_stem(umls_file.stem)
            name_parts = [args.batch_prefix, stem]
            if args.date:
                name_parts.insert(0, args.date)
            output_name = "-".join(name_parts) + ".puml"
            output_path = str((output_dir / output_name).resolve())
            stats = convert_single(str(umls_file.resolve()), output_path, workspace)
            converted += 1
            print(
                "converted",
                f"input={umls_file}",
                f"output={stats['output']}",
                f"objects={stats['objects']}",
                f"messages={stats['messages']}",
                f"fragments={stats['fragments']}",
            )

        print("done", f"files={converted}")
        return 0

    stats = convert_single(
        os.path.abspath(args.input),
        os.path.abspath(args.output),
        workspace,
    )
    print(
        "done",
        f"objects={stats['objects']}",
        f"messages={stats['messages']}",
        f"fragments={stats['fragments']}",
        f"output={stats['output']}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())