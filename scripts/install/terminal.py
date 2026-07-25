"""Terminal selection policy and arrow-key install UI."""

from __future__ import annotations

import argparse
import sys
import termios
import tty
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set, TextIO, Tuple

from .common import InstallerError


CLEAR = "\x1b[2J\x1b[H"
HIDE_CURSOR = "\x1b[?25l"
SHOW_CURSOR = "\x1b[?25h"


@dataclass
class HostInstallPlan:
    host: str
    components: List[str]
    reset_before_install: bool = False
    reset_templates: bool = False


@dataclass
class _HostState:
    host: str
    label: str
    version: str
    available: bool
    enabled: bool
    components: Sequence[Dict[str, Any]]
    selected: Set[str]
    reset: bool = False
    reset_templates: bool = False


def csv_items(value: str) -> List[str]:
    return list(dict.fromkeys(item for item in value.split(",") if item))


def csv_value(items: Iterable[str]) -> str:
    return ",".join(items)


def _read_key(stream: TextIO) -> str:
    value = stream.read(1)
    if value == "\x1b":
        tail = stream.read(2)
        if tail == "[A":
            return "up"
        if tail == "[B":
            return "down"
        return ""
    if value in ("k", "K"):
        return "up"
    if value in ("j", "J"):
        return "down"
    if value == " ":
        return "toggle"
    if value in ("\r", "\n"):
        return "enter"
    if value in ("q", "Q"):
        return "exit"
    return ""


def _rows(states: Sequence[_HostState]) -> List[Tuple[str, int, int]]:
    rows = []
    for host_index, state in enumerate(states):
        rows.append(("header", host_index, -1))
        if not state.available:
            continue
        rows.append(("host", host_index, -1))
        for component_index, _ in enumerate(state.components):
            rows.append(("component", host_index, component_index))
        rows.append(("reset", host_index, -1))
        rows.append(("template", host_index, -1))
    rows.extend((("install", -1, -1), ("exit", -1, -1)))
    return rows


def _render(
    output: TextIO,
    states: Sequence[_HostState],
    rows: Sequence[Tuple[str, int, int]],
    cursor: int,
) -> None:
    output.write(CLEAR)
    output.write("hukuhaka-harness installer\n")
    output.write("  Up/Down move  Space select  Enter apply  q exit\n\n")
    for row_index, (kind, host_index, component_index) in enumerate(rows):
        marker = "> " if row_index == cursor else "  "
        if kind == "header":
            state = states[host_index]
            if state.available:
                detail = "detected{}".format(
                    " ({})".format(state.version) if state.version else ""
                )
            else:
                detail = "unavailable ({} CLI not found)".format(state.host)
            output.write("{} — {}\n".format(state.label, detail))
            continue
        if kind == "install":
            output.write("\n{}Install\n".format(marker))
            continue
        if kind == "exit":
            output.write("{}Exit\n".format(marker))
            continue

        state = states[host_index]
        if kind == "host":
            output.write("{}[{}] Install/update\n".format(marker, "x" if state.enabled else " "))
        elif kind == "component":
            component = state.components[component_index]
            checked = component["name"] in state.selected
            output.write(
                "{}    [{}] {} ({})\n".format(
                    marker,
                    "x" if checked else " ",
                    component["name"],
                    component["kind"],
                )
            )
        elif kind == "reset":
            output.write(
                "{}    [{}] Reset managed plugins/skills before install\n".format(
                    marker, "x" if state.reset else " "
                )
            )
        elif kind == "template":
            output.write(
                "{}    [{}] Reset managed instruction template too\n".format(
                    marker, "x" if state.reset_templates else " "
                )
            )
    output.flush()


def prompt_install_plan(
    input_stream: TextIO,
    output_stream: TextIO,
    *,
    sections: Sequence[Dict[str, Any]],
    keys: Optional[Iterable[str]] = None,
) -> List[HostInstallPlan]:
    states = [
        _HostState(
            host=str(section["host"]),
            label=str(section["label"]),
            version=str(section.get("version", "")),
            available=bool(section.get("available")),
            enabled=bool(section.get("available")),
            components=list(section["components"]),
            selected=set(section["selected"]),
        )
        for section in sections
    ]
    rows = _rows(states)
    selectable = [index for index, row in enumerate(rows) if row[0] != "header"]
    cursor_position = 0
    cursor = selectable[cursor_position]
    key_iterator = iter(keys) if keys is not None else None
    file_descriptor = None
    previous = None
    if key_iterator is None:
        file_descriptor = input_stream.fileno()
        previous = termios.tcgetattr(file_descriptor)
        tty.setcbreak(file_descriptor)
        output_stream.write(HIDE_CURSOR)

    try:
        while True:
            _render(output_stream, states, rows, cursor)
            key = next(key_iterator, "exit") if key_iterator is not None else _read_key(input_stream)
            if key == "up":
                cursor_position = (cursor_position - 1) % len(selectable)
            elif key == "down":
                cursor_position = (cursor_position + 1) % len(selectable)
            elif key == "exit":
                return []
            elif key in ("toggle", "enter"):
                kind, host_index, component_index = rows[cursor]
                if kind == "install":
                    return [
                        HostInstallPlan(
                            host=state.host,
                            components=[
                                str(component["name"])
                                for component in state.components
                                if component["name"] in state.selected
                            ],
                            reset_before_install=state.reset,
                            reset_templates=state.reset_templates,
                        )
                        for state in states
                        if state.available and state.enabled and state.selected
                    ]
                if kind == "exit":
                    return []
                state = states[host_index]
                if kind == "host":
                    state.enabled = not state.enabled
                elif kind == "component" and state.enabled:
                    name = str(state.components[component_index]["name"])
                    if name in state.selected:
                        state.selected.remove(name)
                    else:
                        state.selected.add(name)
                elif kind == "reset" and state.enabled:
                    state.reset = not state.reset
                    if not state.reset:
                        state.reset_templates = False
                elif kind == "template" and state.enabled and state.reset:
                    state.reset_templates = not state.reset_templates
            cursor = selectable[cursor_position]
    finally:
        if file_descriptor is not None and previous is not None:
            termios.tcsetattr(file_descriptor, termios.TCSADRAIN, previous)
            output_stream.write(SHOW_CURSOR + "\n")
            output_stream.flush()


def choose_components(
    *,
    args: argparse.Namespace,
    available: Sequence[Dict[str, Any]],
    current: Set[str],
    validate_names: Callable[[Iterable[str]], List[str]],
    component_map: Dict[str, Dict[str, Any]],
) -> List[str]:
    if args.all:
        selected = [
            str(component["name"])
            for component in available
            if component.get("default") is True and component.get("lifecycle") == "supported"
        ]
    elif args.components is not None:
        selected = validate_names(csv_items(args.components))
    elif args.add or args.remove:
        add = validate_names(csv_items(args.add)) if args.add else []
        remove = validate_names(csv_items(args.remove)) if args.remove else []
        selected_set = (current | set(add)) - set(remove)
        order = [str(component["name"]) for component in available]
        selected = [name for name in order if name in selected_set]
    else:
        defaults = {
            str(component["name"])
            for component in available
            if component.get("default") is True
            and component.get("lifecycle") == "supported"
        }
        selected_set = current | defaults
        order = [str(component["name"]) for component in available]
        selected = [name for name in order if name in selected_set]
        print(
            "No interactive terminal detected; preserving current components "
            "and adding supported defaults.",
            file=sys.stderr,
        )

    selected = validate_names(selected)
    if not selected:
        raise InstallerError(
            "empty selection rejected; use --uninstall to remove everything",
            stage="component-selection",
        )
    deprecated = [
        name for name in selected if component_map[name].get("lifecycle") == "deprecated"
    ]
    if deprecated:
        print(
            "Warning: deprecated component(s) selected: {}".format(csv_value(deprecated)),
            file=sys.stderr,
        )
    return selected
