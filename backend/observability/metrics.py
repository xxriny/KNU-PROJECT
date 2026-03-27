"""
파이프라인 노드 메트릭 (REQ-005, REQ-006)
prometheus_client 기반 노드별 latency/failure 수집.
/metrics 엔드포인트용 ASGI 앱도 제공.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Generator

try:
    from prometheus_client import (
        Counter,
        Histogram,
        make_asgi_app as _make_asgi_app,
        CONTENT_TYPE_LATEST,
        generate_latest,
        REGISTRY,
    )

    NODE_LATENCY: Histogram = Histogram(
        "pipeline_node_latency_seconds",
        "Pipeline node execution latency in seconds",
        ["node_name", "action_type"],
    )

    NODE_FAILURE: Counter = Counter(
        "pipeline_node_failures_total",
        "Total pipeline node failures",
        ["node_name", "action_type"],
    )

    def make_metrics_app():
        """Prometheus scrape용 ASGI 앱 반환."""
        return _make_asgi_app()

    @contextmanager
    def track_node(node_name: str, action_type: str = "unknown") -> Generator:
        """노드 실행을 감싸며 latency와 failure를 자동 기록하는 context manager."""
        start = time.perf_counter()
        try:
            yield
        except Exception:
            NODE_FAILURE.labels(node_name=node_name, action_type=action_type).inc()
            raise
        finally:
            elapsed = time.perf_counter() - start
            NODE_LATENCY.labels(node_name=node_name, action_type=action_type).observe(elapsed)

except ImportError:
    # prometheus_client 미설치 시 no-op 폴백
    from contextlib import contextmanager as _cm

    class _NoopHistogram:
        def labels(self, **_):
            return self
        def observe(self, *_):
            pass

    class _NoopCounter:
        def labels(self, **_):
            return self
        def inc(self, *_):
            pass

    NODE_LATENCY = _NoopHistogram()  # type: ignore[assignment]
    NODE_FAILURE = _NoopCounter()    # type: ignore[assignment]

    def make_metrics_app():  # type: ignore[misc]
        return None

    @_cm
    def track_node(node_name: str, action_type: str = "unknown") -> Generator:  # type: ignore[misc]
        yield
