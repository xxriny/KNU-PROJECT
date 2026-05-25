from __future__ import annotations

import json
import os
import sys
import time
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from pipeline.core.cost_manager import calculate_cost
from pipeline.domain.dev_tracking.service import run_dev_tracking_analysis
from pipeline.domain.dev_tracking.test.judge.dev_tracking_judge import judge_dev_tracking_result


load_dotenv()


def _load_scenarios() -> list[dict[str, Any]]:
    scenario_path = Path(__file__).with_name("scenarios.json")
    return json.loads(scenario_path.read_text(encoding="utf-8"))


def _should_run_judge() -> bool:
    return os.getenv("RUN_DEV_TRACKING_JUDGE", "").strip().lower() in {"1", "true", "yes"}


def _resolve_source_dir() -> Path:
    # author: xxrin
    # 기본 benchmark는 현재 workspace의 git repo를 사용해 원격 clone 없이 재현 가능해야 한다.
    override = os.getenv("DEV_TRACKING_SOURCE_DIR", "").strip()
    if override:
        return Path(override).resolve()
    return Path(__file__).resolve().parents[6]


def _resolve_head_sha(source_dir: Path) -> str:
    override = os.getenv("DEV_TRACKING_HEAD_SHA", "").strip()
    if override:
        return override
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(source_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if completed.returncode == 0:
            return completed.stdout.strip()
    except Exception:
        pass
    return ""


def _write_report(results: list[dict[str, Any]], *, dry_run: bool) -> Path:
    # author: xxrin
    # LLM judge 결과와 deterministic 실행 결과를 분리해 추적할 수 있도록 Markdown 리포트로 남긴다.
    report_dir = Path(__file__).with_name("reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = report_dir / f"dev_tracking_benchmark_{timestamp}.md"

    lines = [
        "# Dev Tracking Benchmark Report",
        "",
        f"- Execution Time: {datetime.now().isoformat()}",
        f"- Judge Enabled: {not dry_run}",
        f"- Judge Model: {os.getenv('DEV_TRACKING_JUDGE_MODEL', 'gemini-2.5-flash')}",
        "",
        "## Scenario Results",
        "",
    ]
    for item in results:
        scenario = item["scenario"]
        judge = item.get("judge") or {}
        lines.extend(
            [
                f"### {scenario['id']} - {scenario['name']}",
                f"- Pipeline Status: `{item.get('status')}`",
                f"- Latency: {item.get('latency_sec', 0):.2f}s",
                f"- Judge Passed: `{judge.get('passed', 'SKIPPED')}`",
                f"- Scores: `{json.dumps(judge.get('scores', {}), ensure_ascii=False)}`",
                f"- Feedback: {judge.get('overall_feedback', 'Judge skipped')}",
                "",
            ]
        )
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def run_dev_tracking_benchmark(*, target_model: str = "") -> list[dict[str, Any]]:
    # author: xxrin
    # 이 harness는 일반 pytest가 아니라 수동 품질 평가용이다. RUN_DEV_TRACKING_JUDGE=1일 때만 LLM judge를 호출한다.
    judge_enabled = _should_run_judge()
    scenarios = _load_scenarios()
    api_key = os.getenv("GEMINI_API_KEY", "")
    target_model = target_model or os.getenv("DEFAULT_MODEL", "gemini-2.5-flash")
    judge_model = os.getenv("DEV_TRACKING_JUDGE_MODEL", "gemini-2.5-flash")
    results: list[dict[str, Any]] = []

    for scenario in scenarios:
        print(f"[DevTrackingBench] Running {scenario['id']} - {scenario['name']}")
        payload = dict(scenario.get("payload") or {})
        source_dir = _resolve_source_dir()
        payload.setdefault("source_dir", str(source_dir))
        payload.setdefault("repository", {"owner": "local", "repo": "workspace"})
        payload.setdefault("pull_request", {})
        if isinstance(payload.get("pull_request"), dict):
            payload["pull_request"] = dict(payload["pull_request"])
            payload["pull_request"]["head_sha"] = _resolve_head_sha(source_dir)
        payload["api_key"] = api_key
        payload["model"] = target_model
        started = time.time()
        try:
            pipeline_result = run_dev_tracking_analysis(payload)
            latency = time.time() - started
            judge_payload = None
            if judge_enabled:
                judge_output = judge_dev_tracking_result(
                    scenario=scenario,
                    result=pipeline_result,
                    judge_model=judge_model,
                    api_key=api_key,
                )
                judge_payload = judge_output.model_dump() if judge_output else None
            results.append(
                {
                    "scenario": scenario,
                    "status": pipeline_result.get("status"),
                    "latency_sec": latency,
                    "result": pipeline_result,
                    "judge": judge_payload,
                    "estimated_judge_cost": calculate_cost(judge_model, 0, 0) if judge_enabled else 0.0,
                }
            )
        except Exception as exc:
            results.append(
                {
                    "scenario": scenario,
                    "status": "ERROR",
                    "latency_sec": time.time() - started,
                    "error": str(exc) or type(exc).__name__,
                    "judge": None,
                }
            )

    report = _write_report(results, dry_run=not judge_enabled)
    print(f"[DevTrackingBench] Report created: {report}")
    return results


if __name__ == "__main__":
    run_dev_tracking_benchmark()
