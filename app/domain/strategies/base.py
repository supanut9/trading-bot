from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class Signal:
    action: str
    reason: str


class Strategy(Protocol):
    def evaluate(self) -> Signal | None:
        """Evaluate the strategy and return a signal when conditions are met."""
