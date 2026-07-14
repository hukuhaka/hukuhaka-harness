"""Installer error types with stable user-facing context."""

from __future__ import annotations

from typing import Optional


class InstallerError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        host: Optional[str] = None,
        stage: Optional[str] = None,
        operation: Optional[str] = None,
        path: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.host = host
        self.stage = stage
        self.operation = operation
        self.path = path

    def render(self) -> str:
        context = []
        if self.host:
            context.append("host={}".format(self.host))
        if self.stage:
            context.append("stage={}".format(self.stage))
        if self.operation:
            context.append("operation={}".format(self.operation))
        if self.path:
            context.append("path={}".format(self.path))
        prefix = "installer"
        if context:
            prefix += " [{}]".format(" ".join(context))
        return "{}: {}".format(prefix, self)


class StateError(InstallerError):
    pass


class DriftError(InstallerError):
    pass
