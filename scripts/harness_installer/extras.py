"""Safe Claude settings mutations for optional installer extras."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from .errors import InstallerError, StateError
from .filesystem import FileTransaction, InstallerLock, load_json


class ExtrasSettings:
    def __init__(self, claude_dir: Path) -> None:
        self.claude_dir = claude_dir
        self.settings_path = claude_dir / "settings.json"
        self.legacy_statusline = claude_dir / "statusline.sh"

    def load(self) -> Dict[str, Any]:
        settings = load_json(self.settings_path, {})
        if not isinstance(settings, dict):
            raise StateError(
                "Claude settings must be a JSON object",
                operation="read-extras-settings",
                path=str(self.settings_path),
            )
        return settings

    @staticmethod
    def statusline_command(settings: Dict[str, Any]) -> str:
        statusline = settings.get("statusLine") or {}
        if not isinstance(statusline, dict):
            raise StateError("Claude settings statusLine must be an object", operation="inspect-extras")
        return str(statusline.get("command", ""))

    @staticmethod
    def has_rtk_hook(settings: Dict[str, Any]) -> bool:
        hooks = settings.get("hooks") or {}
        if not isinstance(hooks, dict):
            raise StateError("Claude settings hooks must be an object", operation="inspect-extras")
        pre_tool = hooks.get("PreToolUse") or []
        if not isinstance(pre_tool, list):
            raise StateError("Claude settings PreToolUse hooks must be an array", operation="inspect-extras")
        for hook in pre_tool:
            if not isinstance(hook, dict) or hook.get("matcher") != "Bash":
                continue
            handlers = hook.get("hooks") or []
            if not isinstance(handlers, list):
                raise StateError("Claude hook handlers must be an array", operation="inspect-extras")
            for handler in handlers:
                if isinstance(handler, dict) and "rtk hook" in str(handler.get("command", "")):
                    return True
        return False

    def inspect(self, field: str) -> bool:
        settings = self.load()
        if field == "statusline":
            return "ccstatusline" in self.statusline_command(settings)
        if field == "statusline-entry":
            return "statusLine" in settings
        if field == "rtk-hook":
            return self.has_rtk_hook(settings)
        raise InstallerError("unknown extras field: {}".format(field), stage="extras")

    def _remove_statusline(self, settings: Dict[str, Any]) -> bool:
        return settings.pop("statusLine", None) is not None

    def _remove_rtk_hook(self, settings: Dict[str, Any]) -> bool:
        hooks = settings.get("hooks") or {}
        if not isinstance(hooks, dict):
            raise StateError("Claude settings hooks must be an object", operation="remove-rtk-hook")
        pre_tool = hooks.get("PreToolUse") or []
        if not isinstance(pre_tool, list):
            raise StateError("Claude settings PreToolUse hooks must be an array", operation="remove-rtk-hook")
        changed = False
        retained = []
        for hook in pre_tool:
            if not isinstance(hook, dict) or hook.get("matcher") != "Bash":
                retained.append(hook)
                continue
            handlers = hook.get("hooks") or []
            if not isinstance(handlers, list):
                raise StateError("Claude hook handlers must be an array", operation="remove-rtk-hook")
            kept = [
                handler
                for handler in handlers
                if not isinstance(handler, dict)
                or "rtk hook" not in str(handler.get("command", ""))
            ]
            changed = changed or len(kept) != len(handlers)
            if kept:
                updated = dict(hook)
                updated["hooks"] = kept
                retained.append(updated)
        if retained:
            hooks["PreToolUse"] = retained
        else:
            hooks.pop("PreToolUse", None)
        if hooks:
            settings["hooks"] = hooks
        else:
            settings.pop("hooks", None)
        return changed

    def mutate(self, action: str, *, dry_run: bool) -> bool:
        settings = self.load()
        remove_legacy = False
        if action == "remove-statusline":
            changed = self._remove_statusline(settings)
        elif action == "remove-rtk-hook":
            changed = self._remove_rtk_hook(settings)
        elif action == "migrate-legacy":
            command = self.statusline_command(settings)
            stale = command.endswith("statusline.sh") and "ccstatusline" not in command
            changed = self._remove_statusline(settings) if stale else False
            remove_legacy = self.legacy_statusline.is_file()
            changed = changed or remove_legacy
        else:
            raise InstallerError("unknown extras action: {}".format(action), stage="extras")
        if dry_run or not changed:
            return changed

        self.claude_dir.mkdir(parents=True, exist_ok=True)
        with InstallerLock(self.claude_dir):
            FileTransaction.recover_pending(self.claude_dir)
            with FileTransaction(self.claude_dir) as transaction:
                if self.settings_path.exists():
                    transaction.write_json(self.settings_path, settings)
                if remove_legacy:
                    transaction.remove(self.legacy_statusline)
                transaction.commit()
        return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect or update optional Claude extras")
    parser.add_argument("action", choices=("inspect", "remove-statusline", "remove-rtk-hook", "migrate-legacy"))
    parser.add_argument("--field", choices=("statusline", "statusline-entry", "rtk-hook"))
    parser.add_argument("--claude-dir", type=Path, default=Path.home() / ".claude")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manager = ExtrasSettings(args.claude_dir)
        if args.action == "inspect":
            if not args.field:
                raise InstallerError("inspect requires --field", stage="extras")
            result = manager.inspect(args.field)
        else:
            result = manager.mutate(args.action, dry_run=args.dry_run)
        print("true" if result else "false")
        return 0
    except InstallerError as exc:
        print(exc.render(), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
