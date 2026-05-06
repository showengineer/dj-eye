from collections.abc import Callable
from dataclasses import dataclass


TransportPosition = float | None
TransportProvider = Callable[[], TransportPosition]
TransportRate = float | None
TransportRateProvider = Callable[[], TransportRate]

@dataclass
class ClockSource:
    transport_provider: TransportProvider
    transport_rate_provider: TransportRateProvider | None = None

    def get_transport_position(self) -> TransportPosition:
        value = self.transport_provider()
        if value is None:
            return None
        if not isinstance(value, (int, float)):
            raise TypeError("ClockSource must return float | int | None")
        return float(value)

    def get_transport_rate(self) -> float:
        if self.transport_rate_provider is None:
            return 1.0
        value = self.transport_rate_provider()
        if value is None:
            return 0.0
        if not isinstance(value, (int, float)):
            raise TypeError("ClockSource rate must return float | int | None")
        return float(value)
