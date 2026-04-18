"""Lightweight in-process metrics. Flushed to Cloud Monitoring by an exporter."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock
from typing import Any


@dataclass
class _Histogram:
    count: int = 0
    sum: float = 0.0

    def record(self, value: float) -> None:
        self.count += 1
        self.sum += value


@dataclass
class InterpreterMetrics:
    """In-process counters and histograms. Thread-safe."""

    _lock: Lock = field(default_factory=Lock)
    _counters: dict[str, dict[str, int]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(int))
    )
    _histograms: dict[str, dict[str, _Histogram]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(_Histogram))
    )
    _gauges: dict[str, float] = field(default_factory=lambda: defaultdict(float))

    def request_count_inc(
        self, *, status: str, language: str, intent_type: str
    ) -> None:
        key = f"{status}|{language}|{intent_type}"
        with self._lock:
            self._counters["interpret.request_count"][key] += 1

    def retry_count_inc(self, *, error_code: str) -> None:
        with self._lock:
            self._counters["interpret.retry_count"][error_code] += 1

    def latency_ms_record(self, *, intent_type: str, value_ms: float) -> None:
        with self._lock:
            self._histograms["interpret.latency_ms"][intent_type].record(value_ms)

    def gemma_tokens_inc(self, *, direction: str, count: int) -> None:
        with self._lock:
            self._counters["interpret.gemma_tokens_total"][direction] += count

    def degraded_mode_set(self, *, active: bool) -> None:
        with self._lock:
            self._gauges["interpret.degraded_mode_active"] = 1.0 if active else 0.0

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                **{k: dict(v) for k, v in self._counters.items()},
                **{
                    k: {kk: {"count": vv.count, "sum": vv.sum}
                        for kk, vv in v.items()}
                    for k, v in self._histograms.items()
                },
                **{k: float(v) for k, v in self._gauges.items()},
            }
