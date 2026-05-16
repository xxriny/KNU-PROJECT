"""
GitHub 커밋 히스토리 분석기.
커밋을 날짜/저자별로 집계하고 주요 변경 패턴을 식별한다.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field


@dataclass
class CommitAnalytics:
    total_commits: int = 0
    by_author: dict[str, int] = field(default_factory=dict)
    by_date: dict[str, int] = field(default_factory=dict)  # YYYY-MM-DD → count
    top_keywords: list[tuple[str, int]] = field(default_factory=list)
    recent_commits: list[dict] = field(default_factory=list)
    activity_trend: str = "stable"  # "increasing" | "decreasing" | "stable"


def analyze_commits(commits: list) -> CommitAnalytics:
    """
    ConnectInfo.CommitInfo 리스트를 분석한다.

    commits: list[CommitInfo] from github_connector
    """
    if not commits:
        return CommitAnalytics()

    by_author: Counter = Counter()
    by_date: Counter = Counter()
    all_words: Counter = Counter()

    recent = []
    for c in commits:
        # author (dataclass or dict 모두 지원)
        author = getattr(c, "author", None) or c.get("author", "") if isinstance(c, dict) else c.author
        date_str = getattr(c, "date", None) or (c.get("date", "") if isinstance(c, dict) else c.date)
        message = getattr(c, "message", None) or (c.get("message", "") if isinstance(c, dict) else c.message)

        by_author[author] += 1
        date_key = date_str[:10] if date_str else "unknown"
        by_date[date_key] += 1

        # 메시지 키워드 추출 (영문 소문자 단어)
        import re
        words = re.findall(r"[a-zA-Z가-힣]{3,}", message.lower())
        stop_words = {"the", "add", "fix", "feat", "update", "merge", "and", "for", "with", "this"}
        for w in words:
            if w not in stop_words:
                all_words[w] += 1

        recent.append({
            "sha": getattr(c, "sha", c.get("sha", "")) if isinstance(c, dict) else c.sha,
            "message": message[:80],
            "author": author,
            "date": date_str[:10] if date_str else "",
        })

    # 활동 트렌드: 첫 절반 vs 후반 비교
    sorted_dates = sorted(by_date.keys())
    half = len(sorted_dates) // 2
    if half > 0:
        first_half = sum(by_date[d] for d in sorted_dates[:half])
        second_half = sum(by_date[d] for d in sorted_dates[half:])
        if second_half > first_half * 1.3:
            trend = "increasing"
        elif second_half < first_half * 0.7:
            trend = "decreasing"
        else:
            trend = "stable"
    else:
        trend = "stable"

    return CommitAnalytics(
        total_commits=len(commits),
        by_author=dict(by_author.most_common(10)),
        by_date=dict(sorted(by_date.items())),
        top_keywords=all_words.most_common(10),
        recent_commits=recent[:10],
        activity_trend=trend,
    )
