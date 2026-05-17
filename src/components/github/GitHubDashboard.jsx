import React, { useState, useEffect } from "react";
import useAppStore from "../../store/useAppStore";
import {
  Github, GitCommit, Users, AlertCircle, BookOpen,
  Loader2, RefreshCw, TrendingUp, TrendingDown, Minus,
  ExternalLink, Tag, Upload, Check, X,
} from "lucide-react";

const TABS = [
  { id: "commits", label: "커밋", Icon: GitCommit },
  { id: "issues",  label: "이슈", Icon: AlertCircle },
  { id: "contributors", label: "기여자", Icon: Users },
  { id: "publish", label: "설계 퍼블리시", Icon: Upload },
];

const TREND_ICON = {
  increasing: <TrendingUp size={14} className="text-emerald-400" />,
  decreasing: <TrendingDown size={14} className="text-red-400" />,
  stable:     <Minus size={14} className="text-slate-400" />,
};

export default function GitHubDashboard() {
  const isDarkMode = useAppStore((s) => s.isDarkMode);
  const githubOwner  = useAppStore((s) => s.githubOwner);
  const githubRepo   = useAppStore((s) => s.githubRepo);
  const githubBranch = useAppStore((s) => s.githubBranch) || "main";
  const resultData  = useAppStore((s) => s.resultData);
  const backendPort = useAppStore((s) => s.backendPort);
  const authToken   = useAppStore((s) => s.authToken);
  const currentUser = useAppStore((s) => s.currentUser);

  const [activeTab, setActiveTab] = useState("commits");
  const [analytics, setAnalytics] = useState(null);
  const [issues, setIssues]       = useState(null);
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState("");
  const [publishStatus, setPublishStatus] = useState(null); // null | "loading" | "ok" | "error"
  const [publishMsg, setPublishMsg] = useState("");

  const port = backendPort || 8000;
  // githubToken은 DB에 저장된 GitHub OAuth 토큰 (backend가 관리)
  // 클라이언트에서 직접 githubToken 없이 현재 사용자의 github_id로 연결 여부 판단
  const isGithubConnected = !!currentUser?.github_id;
  const hasRepoConfig = githubOwner && githubRepo;
  const hasConfig = isGithubConnected && hasRepoConfig;
  const authHeader = { Authorization: `Bearer ${authToken}` };

  const fetchAnalytics = async () => {
    setLoading(true); setError("");
    try {
      const res = await fetch(`http://127.0.0.1:${port}/api/github/analytics`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeader },
        body: JSON.stringify({ owner: githubOwner, repo: githubRepo, branch: githubBranch }),
      });
      const json = await res.json();
      if (json.status === "ok") setAnalytics(json.data);
      else setError(json.error || "분석 실패");
    } catch (e) { setError("연결 실패: " + e.message); }
    finally { setLoading(false); }
  };

  const fetchIssues = async () => {
    setLoading(true); setError("");
    try {
      const res = await fetch(`http://127.0.0.1:${port}/api/github/issues`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeader },
        body: JSON.stringify({ owner: githubOwner, repo: githubRepo }),
      });
      const json = await res.json();
      if (json.status === "ok") setIssues(json.data);
      else setError(json.error || "조회 실패");
    } catch (e) { setError("연결 실패: " + e.message); }
    finally { setLoading(false); }
  };

  // 컴포넌트 마운트 또는 GitHub 설정/브랜치 변경 시 현재 탭 데이터 자동 로드
  useEffect(() => {
    if (!hasConfig) return;
    setAnalytics(null);
    setIssues(null);
    if (activeTab === "commits" || activeTab === "contributors") {
      fetchAnalytics();
    } else if (activeTab === "issues") {
      fetchIssues();
    }
  }, [hasConfig, githubBranch]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleTabChange = (tab) => {
    setActiveTab(tab);
    setError("");
    if (tab === "commits" && !analytics) fetchAnalytics();
    if (tab === "issues" && !issues) fetchIssues();
    if (tab === "contributors" && !analytics) fetchAnalytics();
  };

  const handlePublish = async () => {
    if (!resultData) { setPublishMsg("분석 결과가 없습니다."); setPublishStatus("error"); return; }
    setPublishStatus("loading");
    try {
      const res = await fetch(`http://127.0.0.1:${port}/api/github/publish`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeader },
        body: JSON.stringify({
          owner: githubOwner, repo: githubRepo,
          result_data: resultData,
          page_title: "SA 설계 문서",
          project_name: resultData?.pm_bundle?.project_name || "Project",
        }),
      });
      const json = await res.json();
      if (json.status === "ok") {
        setPublishStatus("ok");
        setPublishMsg(`${json.action === "created" ? "생성" : "업데이트"} 완료 (Issue #${json.number})`);
      } else {
        setPublishStatus("error");
        setPublishMsg(json.error || "퍼블리시 실패");
      }
    } catch (e) { setPublishStatus("error"); setPublishMsg("연결 실패: " + e.message); }
  };

  if (!isGithubConnected) {
    return (
      <div className={`h-full flex flex-col items-center justify-center gap-4 p-8 opacity-60 ${isDarkMode ? "text-slate-300" : "text-slate-700"}`}>
        <Github size={64} />
        <p className="text-lg font-bold">GitHub 로그인이 필요합니다</p>
        <p className="text-sm text-center">설정 패널에서 GitHub 계정을 연결하세요.</p>
      </div>
    );
  }

  if (!hasRepoConfig) {
    return (
      <div className={`h-full flex flex-col items-center justify-center gap-4 p-8 opacity-60 ${isDarkMode ? "text-slate-300" : "text-slate-700"}`}>
        <Github size={64} />
        <p className="text-lg font-bold">대상 레포지토리가 필요합니다</p>
        <p className="text-sm text-center">설정 패널에서 분석할 레포지토리를 선택하세요.</p>
      </div>
    );
  }

  return (
    <div className={`h-full flex flex-col p-6 space-y-5 ${isDarkMode ? "text-slate-300" : "text-slate-800"}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className={`text-2xl font-black tracking-tight flex items-center gap-2 ${isDarkMode ? "text-white" : "text-slate-900"}`}>
            <Github size={22} /> {githubOwner}/{githubRepo}
          </h2>
          <p className="text-sm opacity-60 mt-1">GitHub 통합 대시보드</p>
        </div>
        <button
          onClick={() => activeTab === "issues" ? fetchIssues() : fetchAnalytics()}
          disabled={loading}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-bold transition-all ${
            isDarkMode ? "bg-white/5 hover:bg-white/10" : "bg-slate-100 hover:bg-slate-200 border border-slate-200"
          }`}
        >
          {loading ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
          새로고침
        </button>
      </div>

      {/* Tab Bar */}
      <div className={`flex gap-1 p-1 rounded-xl ${isDarkMode ? "bg-white/5" : "bg-slate-100"}`}>
        {TABS.map(({ id, label, Icon }) => (
          <button
            key={id}
            onClick={() => handleTabChange(id)}
            className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-bold transition-all ${
              activeTab === id
                ? isDarkMode
                  ? "bg-white/10 text-white shadow"
                  : "bg-white text-slate-900 shadow-sm"
                : isDarkMode
                ? "text-slate-500 hover:text-slate-300"
                : "text-slate-500 hover:text-slate-700"
            }`}
          >
            <Icon size={13} /> {label}
          </button>
        ))}
      </div>

      {/* Error */}
      {error && (
        <div className={`p-3 rounded-xl border-l-4 border-red-500 text-sm ${isDarkMode ? "bg-red-500/10 text-red-300" : "bg-red-50 text-red-700"}`}>
          {error}
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-y-auto custom-scrollbar pr-1">
        {loading && (
          <div className="h-40 flex items-center justify-center opacity-40">
            <Loader2 size={32} className="animate-spin" />
          </div>
        )}

        {/* Commits Tab */}
        {!loading && activeTab === "commits" && analytics && (
          <div className="space-y-4 animate-fade-in">
            <div className="grid grid-cols-3 gap-3">
              <StatCard label="총 커밋" value={analytics.total_commits} isDarkMode={isDarkMode} />
              <StatCard label="기여자" value={analytics.contributors?.length || 0} isDarkMode={isDarkMode} />
              <div className={`p-4 rounded-xl border ${isDarkMode ? "bg-white/5 border-white/10" : "bg-white border-slate-200 shadow-sm"}`}>
                <div className="text-xs opacity-50 mb-1">활동 트렌드</div>
                <div className="flex items-center gap-1 font-bold">
                  {TREND_ICON[analytics.activity_trend]}
                  <span className="text-sm capitalize">{analytics.activity_trend}</span>
                </div>
              </div>
            </div>
            <h3 className="text-xs font-bold uppercase tracking-wider opacity-60">최근 커밋</h3>
            <div className="space-y-2">
              {analytics.recent_commits?.map((c, i) => (
                <div key={i} className={`p-3 rounded-xl border ${isDarkMode ? "bg-white/5 border-white/10" : "bg-white border-slate-200 shadow-sm"}`}>
                  <div className="flex items-center gap-2">
                    <span className={`font-mono text-[11px] px-2 py-0.5 rounded ${isDarkMode ? "bg-slate-800 text-slate-400" : "bg-slate-100 text-slate-600"}`}>
                      {c.sha}
                    </span>
                    <span className="text-xs opacity-50">{c.date}</span>
                    <span className={`ml-auto text-xs font-medium ${isDarkMode ? "text-slate-400" : "text-slate-500"}`}>{c.author}</span>
                  </div>
                  <p className="text-sm mt-1.5 font-medium">{c.message}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Issues Tab */}
        {!loading && activeTab === "issues" && issues && (
          <div className="space-y-2 animate-fade-in">
            {issues.length === 0 ? (
              <div className="h-40 flex items-center justify-center opacity-30">
                <p>열린 이슈가 없습니다.</p>
              </div>
            ) : issues.map((issue, i) => (
              <div key={i} className={`p-4 rounded-xl border ${isDarkMode ? "bg-white/5 border-white/10" : "bg-white border-slate-200 shadow-sm"}`}>
                <div className="flex items-start gap-3">
                  <AlertCircle size={16} className="text-emerald-400 mt-0.5 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold text-sm">#{issue.number} {issue.title}</span>
                      {issue.labels?.map((lbl, j) => (
                        <span key={j} className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${isDarkMode ? "bg-blue-500/20 text-blue-300" : "bg-blue-50 text-blue-700"}`}>
                          {lbl}
                        </span>
                      ))}
                    </div>
                    <p className="text-xs opacity-50 mt-1">{issue.author} · {issue.created_at?.slice(0, 10)}</p>
                    {issue.body && <p className="text-xs opacity-60 mt-2 line-clamp-2">{issue.body}</p>}
                  </div>
                  {issue.url && (
                    <a href={issue.url} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:text-blue-300 shrink-0">
                      <ExternalLink size={14} />
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Contributors Tab */}
        {!loading && activeTab === "contributors" && analytics?.contributors && (
          <div className="space-y-2 animate-fade-in">
            {analytics.contributors.map((c, i) => (
              <div key={i} className={`flex items-center gap-3 p-3 rounded-xl border ${isDarkMode ? "bg-white/5 border-white/10" : "bg-white border-slate-200 shadow-sm"}`}>
                <div className={`w-7 h-7 rounded-full flex items-center justify-center font-bold text-xs ${isDarkMode ? "bg-slate-700" : "bg-slate-200"}`}>
                  {i + 1}
                </div>
                <div className="flex-1">
                  <p className="font-semibold text-sm">{c.login}</p>
                </div>
                <div className={`px-3 py-1 rounded-full text-xs font-bold ${isDarkMode ? "bg-blue-500/20 text-blue-300" : "bg-blue-50 text-blue-700"}`}>
                  {c.contributions} commits
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Publish Tab */}
        {activeTab === "publish" && (
          <div className="space-y-5 animate-fade-in">
            <div className={`p-5 rounded-2xl border ${isDarkMode ? "bg-white/5 border-white/10" : "bg-white border-slate-200 shadow-sm"}`}>
              <h3 className="font-bold text-base mb-2">SA 설계 문서 퍼블리시</h3>
              <p className="text-sm opacity-60 mb-4">
                현재 분석 결과(컴포넌트, API, DB)를 GitHub Issues의 `design-doc` 라벨로 퍼블리시합니다.
                이미 같은 제목의 이슈가 있으면 업데이트합니다.
              </p>
              {!resultData && (
                <div className={`p-3 rounded-xl text-sm mb-4 ${isDarkMode ? "bg-amber-500/10 text-amber-300" : "bg-amber-50 text-amber-700"}`}>
                  분석 결과가 없습니다. 먼저 SA 분석을 실행하세요.
                </div>
              )}
              <button
                onClick={handlePublish}
                disabled={publishStatus === "loading" || !resultData}
                className={`flex items-center gap-2 px-5 py-2.5 rounded-xl font-bold text-sm shadow-lg transition-all ${
                  publishStatus === "loading" || !resultData
                    ? "bg-white/5 text-slate-500 cursor-not-allowed"
                    : "bg-slate-800 hover:bg-slate-700 text-white dark:bg-blue-600 dark:hover:bg-blue-500 shadow-blue-500/10"
                }`}
              >
                {publishStatus === "loading" ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <Upload size={16} />
                )}
                {publishStatus === "loading" ? "퍼블리시 중..." : "GitHub에 퍼블리시"}
              </button>
              {publishStatus === "ok" && (
                <p className="mt-3 text-sm text-emerald-400 flex items-center gap-1">
                  <Check size={14} /> {publishMsg}
                </p>
              )}
              {publishStatus === "error" && (
                <p className="mt-3 text-sm text-red-400 flex items-center gap-1">
                  <X size={14} /> {publishMsg}
                </p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({ label, value, isDarkMode }) {
  return (
    <div className={`p-4 rounded-xl border ${isDarkMode ? "bg-white/5 border-white/10" : "bg-white border-slate-200 shadow-sm"}`}>
      <div className="text-xs opacity-50 mb-1">{label}</div>
      <div className={`text-2xl font-black ${isDarkMode ? "text-white" : "text-slate-900"}`}>{value}</div>
    </div>
  );
}
