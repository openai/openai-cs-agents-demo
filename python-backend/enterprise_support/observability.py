from __future__ import annotations

import re
import time
from collections import defaultdict
from contextlib import contextmanager
from threading import RLock
from typing import Iterator


_METRIC_NAME = re.compile(r"^[a-zA-Z_:][a-zA-Z0-9_:]*$")


def _labels(values: dict[str, str]) -> str:
    if not values:
        return ""
    encoded = ",".join(
        f'{key}="{str(value).replace(chr(92), chr(92) * 2).replace(chr(34), chr(92) + chr(34))}"'
        for key, value in sorted(values.items())
    )
    return f"{{{encoded}}}"


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = RLock()
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)
        self._durations: dict[tuple[str, tuple[tuple[str, str], ...]], list[float]] = defaultdict(list)

    @staticmethod
    def _key(name: str, labels: dict[str, str]) -> tuple[str, tuple[tuple[str, str], ...]]:
        if not _METRIC_NAME.match(name):
            raise ValueError(f"Invalid metric name: {name}")
        return name, tuple(sorted((str(key), str(value)) for key, value in labels.items()))

    def increment(self, name: str, *, amount: float = 1, **labels: str) -> None:
        with self._lock:
            self._counters[self._key(name, labels)] += amount

    def observe(self, name: str, seconds: float, **labels: str) -> None:
        with self._lock:
            self._durations[self._key(name, labels)].append(max(seconds, 0))

    @contextmanager
    def timer(self, name: str, **labels: str) -> Iterator[None]:
        started = time.perf_counter()
        try:
            yield
        finally:
            self.observe(name, time.perf_counter() - started, **labels)

    def render_prometheus(self) -> str:
        lines: list[str] = []
        with self._lock:
            counters = sorted(self._counters.items())
            durations = sorted(self._durations.items())
        for (name, label_items), value in counters:
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name}{_labels(dict(label_items))} {value:g}")
        for (name, label_items), values in durations:
            labels = dict(label_items)
            lines.append(f"# TYPE {name} summary")
            lines.append(f"{name}_count{_labels(labels)} {len(values)}")
            lines.append(f"{name}_sum{_labels(labels)} {sum(values):.6f}")
        return "\n".join(lines) + "\n"


METRICS = MetricsRegistry()

