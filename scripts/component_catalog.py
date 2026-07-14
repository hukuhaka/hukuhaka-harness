#!/usr/bin/env python3
"""Query and validate the public hukuhaka component catalog."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


HOSTS = ("claude", "codex")


def load_catalog(root: Path) -> dict:
    with (root / "components.json").open(encoding="utf-8") as handle:
        return json.load(handle)


def selected_hosts(host: str) -> tuple[str, ...]:
    return HOSTS if host == "both" else (host,)


def supports(component: dict, host: str) -> bool:
    return any(name in component.get("hosts", {}) for name in selected_hosts(host))


def component_description(root: Path, component: dict, host: str) -> str:
    if component.get("description"):
        return component["description"]
    for host_name in selected_hosts(host):
        manifest = component.get("hosts", {}).get(host_name, {}).get("manifest")
        if not manifest:
            continue
        with (root / manifest).open(encoding="utf-8") as handle:
            return json.load(handle).get("description", "")
    return ""


def discover(root: Path, catalog: dict, host: str) -> int:
    for component in catalog.get("components", []):
        if not supports(component, host):
            continue
        description = component_description(root, component, host).replace("\t", " ").replace("\n", " ")
        if component.get("lifecycle") == "deprecated":
            description = f"[deprecated] {description}"
        default_on = component.get("default") is True and component.get("lifecycle") == "supported"
        print(
            "\t".join(
                (
                    component["name"],
                    component["kind"],
                    description,
                    "true" if default_on else "false",
                )
            )
        )
    return 0


def filter_components(catalog: dict, host: str, components_csv: str) -> int:
    requested = {name for name in components_csv.split(",") if name}
    names = [
        component["name"]
        for component in catalog.get("components", [])
        if component["name"] in requested and supports(component, host)
    ]
    print(",".join(names))
    return 0


def lifecycle(catalog: dict, components_csv: str, state: str) -> int:
    requested = {name for name in components_csv.split(",") if name}
    names = [
        component["name"]
        for component in catalog.get("components", [])
        if component["name"] in requested and component.get("lifecycle") == state
    ]
    print(",".join(names))
    return 0


def validate(root: Path, catalog: dict) -> int:
    errors: list[str] = []
    if catalog.get("schemaVersion") != 1:
        errors.append("schemaVersion must be 1")
    marketplaces = catalog.get("marketplaces", {})
    if marketplaces.get("claude") != "hukuhaka-plugin":
        errors.append("Claude marketplace name must be hukuhaka-plugin")
    if marketplaces.get("codex") != "hukuhaka-harness":
        errors.append("Codex marketplace name must be hukuhaka-harness")
    components = catalog.get("components", [])
    names = [component.get("name") for component in components]
    if len(names) != len(set(names)):
        errors.append("component names must be unique")

    known_manifests: set[Path] = set()
    for component in components:
        name = component.get("name", "<unnamed>")
        if component.get("kind") not in {"plugin", "skill", "feature", "template"}:
            errors.append(f"{name}: unsupported kind")
        if component.get("lifecycle") not in {"supported", "deprecated"}:
            errors.append(f"{name}: unsupported lifecycle")
        if component.get("lifecycle") == "deprecated" and component.get("default") is True:
            errors.append(f"{name}: deprecated components cannot be default-on")
        hosts = component.get("hosts", {})
        if not hosts or any(host not in HOSTS for host in hosts):
            errors.append(f"{name}: hosts must contain only claude/codex")
        versions: set[str] = set()
        for host, metadata in hosts.items():
            manifest = metadata.get("manifest")
            if not manifest:
                continue
            path = root / manifest
            known_manifests.add(path.resolve())
            if not path.is_file():
                errors.append(f"{name}: missing {host} manifest {manifest}")
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                errors.append(f"{name}: invalid {host} manifest: {exc}")
                continue
            if data.get("name") != name:
                errors.append(f"{name}: {host} manifest name differs")
            version = data.get("version")
            if not version:
                errors.append(f"{name}: {host} manifest has no version")
            else:
                versions.add(version)
        if len(versions) > 1:
            errors.append(f"{name}: host manifest versions differ")
        path_value = component.get("path")
        if path_value and not (root / path_value).is_file():
            errors.append(f"{name}: missing path {path_value}")

    discovered = {
        path.resolve()
        for pattern in ("marketplace/*/.claude-plugin/plugin.json", "marketplace/*/.codex-plugin/plugin.json")
        for path in root.glob(pattern)
    }
    for path in sorted(discovered - known_manifests):
        errors.append(f"uncatalogued manifest: {path.relative_to(root)}")

    marketplace_path = root / ".agents/plugins/marketplace.json"
    try:
        marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"invalid Codex marketplace: {exc}")
    else:
        if marketplace.get("name") != marketplaces.get("codex"):
            errors.append("Codex marketplace name differs from component catalog")
        exposed = {entry.get("name") for entry in marketplace.get("plugins", [])}
        expected = {
            component["name"]
            for component in components
            if component.get("lifecycle") == "supported" and "codex" in component.get("hosts", {})
        }
        if exposed != expected:
            errors.append(f"Codex marketplace entries {sorted(exposed)} != catalog {sorted(expected)}")

    if errors:
        for error in errors:
            print(f"component-catalog: {error}", file=sys.stderr)
        return 1
    print(f"component-catalog: {len(components)} component(s) consistent")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    subparsers = parser.add_subparsers(dest="command", required=True)

    discover_parser = subparsers.add_parser("discover")
    discover_parser.add_argument("--host", choices=("claude", "codex", "both"), required=True)

    filter_parser = subparsers.add_parser("filter")
    filter_parser.add_argument("--host", choices=HOSTS, required=True)
    filter_parser.add_argument("--components", required=True)

    lifecycle_parser = subparsers.add_parser("lifecycle")
    lifecycle_parser.add_argument("--components", required=True)
    lifecycle_parser.add_argument("--state", choices=("supported", "deprecated"), required=True)

    subparsers.add_parser("validate")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    catalog = load_catalog(root)
    if args.command == "discover":
        return discover(root, catalog, args.host)
    if args.command == "filter":
        return filter_components(catalog, args.host, args.components)
    if args.command == "lifecycle":
        return lifecycle(catalog, args.components, args.state)
    return validate(root, catalog)


if __name__ == "__main__":
    raise SystemExit(main())
