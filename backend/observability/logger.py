"""
구조화 로깅 (REQ-004)
structlog 기반 run_id 바인딩 로거.
ENV=dev  → ConsoleRenderer (컬러 출력)
ENV=prod → JSONRenderer (단일 라인 JSON)
"""

from __future__ import annotations

import functools
import os
import logging

try:
    import structlog

    @functools.lru_cache(maxsize=None)
    def _ensure_configured() -> None:
        """프로세스 내 최초 1회 structlog 설정."""
        env = os.environ.get("ENV", "dev").lower()
        renderer = (
            structlog.dev.ConsoleRenderer()
            if env == "dev"
            else structlog.processors.JSONRenderer()
        )
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.stdlib.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                renderer,
            ],
            wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
        )

    def configure_logging() -> None:
        _ensure_configured()

    def get_logger(run_id: str = ""):
        """run_id가 자동 바인딩된 structlog 인스턴스 반환."""
        _ensure_configured()
        logger = structlog.get_logger()
        if run_id:
            logger = logger.bind(run_id=run_id)
        return logger

except ImportError:
    # structlog 미설치 시 표준 logging으로 폴백
    import logging as _logging

    @functools.lru_cache(maxsize=None)
    def _ensure_configured() -> None:
        _logging.basicConfig(
            level=_logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s %(message)s",
        )

    def configure_logging() -> None:  # type: ignore[misc]
        _ensure_configured()

    class _FallbackLogger:
        def __init__(self, run_id: str = ""):
            self._log = _logging.getLogger("pipeline")
            self._run_id = run_id

        def _fmt(self, msg: str, **kw) -> str:
            parts = [msg]
            if self._run_id:
                parts.insert(0, f"run_id={self._run_id}")
            parts += [f"{k}={v}" for k, v in kw.items()]
            return " | ".join(parts)

        def info(self, msg: str, **kw):
            self._log.info(self._fmt(msg, **kw))

        def warning(self, msg: str, **kw):
            self._log.warning(self._fmt(msg, **kw))

        def error(self, msg: str, **kw):
            self._log.error(self._fmt(msg, **kw))

        def bind(self, **kw):
            return self

    def get_logger(run_id: str = ""):  # type: ignore[misc]
        _ensure_configured()
        return _FallbackLogger(run_id=run_id)
