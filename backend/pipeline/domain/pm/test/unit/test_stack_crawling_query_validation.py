"""
Stack Crawling — LLM 생성 검색어(query/pkg) 정규화 공격 회귀 테스트.

AGENTS.md 5.2 작업 항목 3("npm/PyPI/GitHub 검색어 형식과 길이")에 대응한다.
LLM(stack_planner)이 만든 next_crawler_inputs[].query가 검증 없이 그대로
외부 레지스트리 API URL의 경로/쿼리 조각으로 들어가던 문제를 다룬다.

네트워크 호출 없음 — SafeStackClient.fetch_with_retry를 monkeypatch해서
실제로 어떤 URL이 만들어지는지만 검증한다.

실행:
    cd backend
    python -m pytest pipeline/domain/pm/test/unit/test_stack_crawling_query_validation.py -v
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../.."))

from pipeline.domain.pm.nodes import stack_crawling as sc  # noqa: E402


def _capture_urls(monkeypatch):
    """SafeStackClient.fetch_with_retry를 가로채서 요청된 URL만 기록하고 네트워크는 타지 않는다."""
    called_urls = []

    def fake_fetch(self, url, max_retries=3):
        called_urls.append(url)
        return None

    monkeypatch.setattr(sc.SafeStackClient, "fetch_with_retry", fake_fetch)
    return called_urls


def test_path_traversal_query_does_not_reach_registry_url_unsanitized(monkeypatch):
    """'../../etc/passwd' 같은 경로 탈출형 쿼리가 그대로 URL에 삽입되면 안 된다."""
    called_urls = _capture_urls(monkeypatch)

    state = {
        "next_crawler_inputs": [{"target": "npm", "query": "../../../../etc/passwd"}],
    }
    result = sc.stack_crawling_node(state)

    assert result["stack_crawler_output"]["status"] == "Pass"
    npm_calls = [u for u in called_urls if "registry.npmjs.org" in u]
    assert not any(".." in u for u in npm_calls), (
        f"경로 탈출 페이로드가 그대로 npm 요청 URL에 삽입됨: {npm_calls}"
    )


def test_url_structure_injection_query_is_rejected(monkeypatch):
    """'?'/'#' 등으로 요청 구조 자체를 바꾸려는 쿼리는 거부되거나 안전하게 인코딩돼야 한다."""
    called_urls = _capture_urls(monkeypatch)

    malicious_query = "react?redirect=http://attacker.example.com#x"
    state = {
        "next_crawler_inputs": [{"target": "npm", "query": malicious_query}],
    }
    sc.stack_crawling_node(state)

    npm_calls = [u for u in called_urls if "registry.npmjs.org" in u]
    for url in npm_calls:
        assert "attacker.example.com" not in url, (
            f"쿼리 인젝션으로 임의 도메인 문자열이 요청 URL에 그대로 삽입됨: {url}"
        )
        assert "?redirect=" not in url, f"쿼리스트링 구조가 그대로 삽입됨: {url}"


def test_oversized_query_is_rejected(monkeypatch):
    """비정상적으로 긴 쿼리는 길이 제한에서 걸려야 한다."""
    called_urls = _capture_urls(monkeypatch)

    huge_query = "a" * 5000
    state = {
        "next_crawler_inputs": [{"target": "npm", "query": huge_query}],
    }
    sc.stack_crawling_node(state)

    assert not any(len(u) > 300 for u in called_urls), (
        "비정상적으로 긴 쿼리가 길이 제한 없이 그대로 요청 URL에 사용됨"
    )


def test_legitimate_query_still_crawled(monkeypatch):
    """정상 흐름 보존: 평범한 패키지명은 여전히 정상적으로 요청돼야 한다."""
    called_urls = _capture_urls(monkeypatch)

    state = {
        "next_crawler_inputs": [{"target": "npm", "query": "lodash"}],
    }
    sc.stack_crawling_node(state)

    assert any("registry.npmjs.org/lodash/latest" in u for u in called_urls), (
        f"정상 패키지명 'lodash'에 대한 요청이 발생하지 않음: {called_urls}"
    )
