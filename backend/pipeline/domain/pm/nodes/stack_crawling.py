"""
Stack Crawling Node
NPM, GitHub, PyPI 등 기술 스택 메타데이터를 안정적으로 수집합니다.
차단(403), 한도 초과(429) 대응 및 데이터 순도 보장을 포함합니다.
"""

import time
import re
import os
import httpx
from typing import Dict, Any, List, Optional
from pipeline.core.state import PipelineState, make_sget
from pipeline.domain.pm.schemas import StackCrawlingOutput, StackSourceData
from observability.logger import get_logger

logger = get_logger()

# HTML 태그 제거용 정규식
CLEAN_HTML_RE = re.compile('<.*?>|&([a-z0-9]+|#[0-9]{1,6}|#x[0-9a-f]{1,6});')

def clean_html(text: str) -> str:
    """HTML 태그 및 엔티티를 제거하여 순수 텍스트를 반환합니다."""
    if not text:
        return ""
    return re.sub(CLEAN_HTML_RE, '', text).strip()

class SafeStackClient:
    """Retry 및 Rate Limit 처리가 포함된 크롤링 클라이언트"""
    
    def __init__(self, github_token: Optional[str] = None):
        self.headers = {
            "User-Agent": "Navigator-Stack-Crawler/1.0 (Contact: pw710@example.com)",
        }
        if github_token:
            self.headers["Authorization"] = f"token {github_token}"
            
    def fetch_with_retry(self, url: str, max_retries: int = 3) -> Optional[Dict[str, Any]]:
        for attempt in range(max_retries):
            try:
                with httpx.Client(headers=self.headers, timeout=10.0) as client:
                    resp = client.get(url)
                    
                    if resp.status_code == 200:
                        return resp.json()
                    
                    if resp.status_code == 429: # Too Many Requests
                        wait = (2 ** attempt) + 1
                        logger.warning(f"Rate limit hit at {url}. Waiting {wait}s...")
                        time.sleep(wait)
                        continue
                        
                    if resp.status_code == 403: # Forbidden (Likely GitHub Rate Limit or Bot Block)
                        logger.error(f"Access forbidden (403) for {url}. Might be blocked or rate-limited.")
                        return None
                        
                    logger.warning(f"Fetch failed with {resp.status_code} for {url}")
                    return None
                    
            except Exception as e:
                logger.error(f"Error fetching {url}: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
        return None

def _handle_npm(client: SafeStackClient, query: str) -> List[StackSourceData]:
    # NPM 레지스트리 API
    # 현재는 간단한 검색 또는 특정 패키지 검색 기능 제공
    pkg_name = query.split('/')[-1] if '/' in query else query
    url = f"https://registry.npmjs.org/{pkg_name}/latest"
    data = client.fetch_with_retry(url)
    if not data:
        return []
        
    return [StackSourceData(
        name=data.get("name", pkg_name),
        description=clean_html(data.get("description", "")),
        version=data.get("version", "unknown"),
        license=data.get("license", "unknown"),
        last_updated=data.get("publishConfig", {}).get("publishDate", "unknown"), # NPM data is nested
        source_type="npm",
        url=f"https://www.npmjs.com/package/{pkg_name}"
    )]

def _handle_github(client: SafeStackClient, query: str) -> List[StackSourceData]:
    # URL에서 소유자/저장소 정보를 추출하거나 검색어로 쿼리를 사용하세요.
    repo_path = ""
    if "github.com/" in query:
        repo_path = query.split("github.com/")[-1].strip('/')
    else:
        # 직접 URL이 아닌 경우 간단한 검색 API를 사용하세요.
        search_url = f"https://api.github.com/search/repositories?q={query}&sort=stars&order=desc&per_page=1"
        search_data = client.fetch_with_retry(search_url)
        if search_data and search_data.get("items"):
            repo_path = search_data["items"][0]["full_name"]
            
    if not repo_path:
        return []
        
    url = f"https://api.github.com/repos/{repo_path}"
    data = client.fetch_with_retry(url)
    if not data:
        return []
        
    return [StackSourceData(
        name=data.get("name", ""),
        description=clean_html(data.get("description", "")),
        version="unknown", # GitHub API는 별도의 호출 없이는 최신 버전을 쉽게 제공하지 않습니다.
        license=data.get("license", {}).get("name", "unknown") if data.get("license") else "unknown",
        last_updated=data.get("updated_at", "unknown"),
        stars=data.get("stargazers_count", 0),
        source_type="github",
        url=data.get("html_url", "")
    )]

def _handle_pypi(client: SafeStackClient, query: str) -> List[StackSourceData]:
    pkg_name = query.strip()
    url = f"https://pypi.org/pypi/{pkg_name}/json"
    data = client.fetch_with_retry(url)
    if not data or "info" not in data:
        return []
        
    info = data["info"]
    return [StackSourceData(
        name=info.get("name", pkg_name),
        description=clean_html(info.get("summary", "")),
        version=info.get("version", "unknown"),
        license=info.get("license", "unknown"),
        last_updated="unknown", # PyPI JSON은 날짜 관련 내용이 복잡합니다.
        source_type="pypi",
        url=info.get("package_url", "")
    )]

def stack_crawling_node(state: PipelineState) -> Dict[str, Any]:
    sget = make_sget(state)
    logger.info("Starting stack_crawling_node")
    
    # 1. 입력 모드 결정 (Planner의 루프 요청 vs 초기 쿼리)
    # Planner가 구체적으로 생성한 next_crawler_inputs가 있는지 확인
    next_inputs = sget("next_crawler_inputs", [])
    queries_to_crawl = []
    
    if next_inputs:
        # Planner가 준 명확한 타겟과 쿼리 사용
        for item in next_inputs:
            queries_to_crawl.append(item.get("query"))
            
    # 만약 루프 요청이 없다면 기존 단일 input 방식 사용 (초기 진입)
    if not queries_to_crawl:
        crawler_input = sget("stack_crawler_input", {})
        query = crawler_input.get("query")
        if query:
            queries_to_crawl = [query]

    if not queries_to_crawl:
        logger.warning("No queries to crawl.")
        return {"stack_crawler_output": {"status": "Pass", "results": [], "thinking": "검색어가 없어 크롤링을 생략함."}}

    client = SafeStackClient(github_token=os.environ.get("GITHUB_TOKEN"))
    all_results = []
    
    try:
        # 2. 모든 대상 쿼리에 대해 크롤링 수행
        for current_query in queries_to_crawl:
            logger.info(f"Crawling for: {current_query}")
            # 여러 소스를 찔러서 종합 세트로 반환
            for handler in [_handle_npm, _handle_github, _handle_pypi]:
                try:
                    res = handler(client, current_query)
                    if res:
                        all_results.extend(res)
                except Exception as e:
                    logger.warning(f"Handler {handler.__name__} failed for {current_query}: {e}")

        thinking_msg = f"{len(queries_to_crawl)}개의 항목에 대해 총 {len(all_results)}개의 메타데이터를 수집함."
        
        return {
            "stack_crawler_output": {
                "status": "Pass",
                "results": [r.model_dump() for r in all_results],
                "thinking": thinking_msg
            },
            "thinking_log": (sget("thinking_log", []) or []) + [{"node": "stack_crawling", "thinking": thinking_msg}]
        }
        
    except Exception as e:
        logger.exception("stack_crawling_node critical failure")
        return {
            "stack_crawler_output": {
                "status": "Error",
                "results": [],
                "error_message": f"Critical error: {str(e)}",
                "thinking": f"Node failed: {e}"
            }
        }
