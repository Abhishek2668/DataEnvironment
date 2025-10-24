"""Simple Prometheus-like metrics helpers without external dependencies."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Tuple

CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"


@dataclass
class _ChildMetric:
    registry: "BaseMetric"
    label_values: Tuple[str, ...]

    def inc(self, amount: float = 1.0) -> None:
        self.registry._values[self.label_values] += amount

    def set(self, value: float) -> None:
        self.registry._values[self.label_values] = value


class BaseMetric:
    def __init__(self, name: str, description: str, labelnames: Iterable[str] | None = None) -> None:
        self.name = name
        self.description = description
        self.labelnames = tuple(labelnames or [])
        self._values: defaultdict[Tuple[str, ...], float] = defaultdict(float)

    def labels(self, *values: str, **kw: str) -> _ChildMetric:
        if values and kw:
            raise ValueError("use positional or keyword labels, not both")
        if kw:
            ordered = tuple(kw[name] for name in self.labelnames)
        else:
            ordered = tuple(values)
        if len(ordered) != len(self.labelnames):
            raise ValueError("label count mismatch")
        return _ChildMetric(self, ordered)

    def samples(self) -> list[tuple[Tuple[str, ...], float]]:
        return list(self._values.items())


class Counter(BaseMetric):
    def inc(self, amount: float = 1.0) -> None:
        self._values[()] += amount


class Gauge(BaseMetric):
    def set(self, value: float) -> None:
        self._values[()] = value


_METRICS: list[BaseMetric] = []


def register(metric: BaseMetric) -> BaseMetric:
    _METRICS.append(metric)
    return metric


def generate_latest() -> bytes:
    lines: list[str] = []
    for metric in _METRICS:
        lines.append(f"# HELP {metric.name} {metric.description}")
        lines.append(f"# TYPE {metric.name} gauge")
        if metric.labelnames:
            for labels, value in metric.samples():
                label_str = ",".join(f"{name}=\"{val}\"" for name, val in zip(metric.labelnames, labels))
                lines.append(f"{metric.name}{{{label_str}}} {value}")
        else:
            value = metric.samples()[0][1] if metric.samples() else 0.0
            lines.append(f"{metric.name} {value}")
    return "\n".join(lines).encode("utf-8")


__all__ = ["Counter", "Gauge", "generate_latest", "CONTENT_TYPE_LATEST", "register"]
