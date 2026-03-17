from typing import Protocol


class ExecutionService(Protocol):
    def execute(self, request: object) -> object: ...


class ExecutionUnavailableError(RuntimeError):
    """Raised when the selected execution mode has no configured adapter."""
