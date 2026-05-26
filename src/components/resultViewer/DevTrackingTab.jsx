import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleDot,
  GitPullRequest,
  Loader2,
  Play,
  RefreshCw,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import useAppStore from "../../store/useAppStore";
import { serverRequest } from "../../api/serverClient";

const DEFAULT_FORM = {
  owner: "",
  repo: "",
  pr_number: "",
  branch_name: "",
  base_branch: "main",
  head_sha: "",
  source_dir: "",
  notify_pr: false,
  use_llm_forensic_profiler: true,
  use_llm_gap_analyzer: true,
  use_llm_intent_classifier: true,
};

function statusTone(status) {
  const value = String(status || "").toUpperCase();
  if (["PASS", "OK", "SUCCESS", "COMPLETE", "COMPLETED", "APPROVED_INTENTIONAL_CHANGE", "NO_GAP_DETECTED"].includes(value)) {
    return "text-emerald-400 bg-emerald-500/10 border-emerald-500/25";
  }
  if (["FAIL", "ERROR", "BLOCKED", "REJECTED_UNINTENTIONAL_CHANGE"].includes(value)) {
    return "text-red-400 bg-red-500/10 border-red-500/25";
  }
  if (value === "HIGH") {
    return "text-red-400 bg-red-500/10 border-red-500/25";
  }
  if (value === "MED") {
    return "text-amber-400 bg-amber-500/10 border-amber-500/25";
  }
  if (value === "LOW") {
    return "text-emerald-400 bg-emerald-500/10 border-emerald-500/25";
  }
  if (["WARN", "WARNING", "SKIPPED", "PENDING_PM_APPROVAL"].includes(value)) {
    return "text-amber-400 bg-amber-500/10 border-amber-500/25";
  }
  return "text-slate-400 bg-slate-500/10 border-slate-500/20";
}

function nodeIcon(status) {
  const value = String(status || "").toUpperCase();
  if (["PASS", "OK", "SUCCESS"].includes(value)) return CheckCircle2;
  if (["FAIL", "ERROR", "BLOCKED"].includes(value)) return XCircle;
  if (["WARN", "WARNING"].includes(value)) return AlertTriangle;
  return CircleDot;
}

export default function DevTrackingTab() {
  const isDarkMode = useAppStore((state) => state.isDarkMode);
  const backendPort = useAppStore((state) => state.backendPort);
  const authToken = useAppStore((state) => state.authToken);
  const apiKey = useAppStore((state) => state.apiKey) || "";
  const currentUser = useAppStore((state) => state.currentUser);
  const githubOwner = useAppStore((state) => state.githubOwner);
  const githubRepo = useAppStore((state) => state.githubRepo);
  const githubBranch = useAppStore((state) => state.githubBranch) || "main";
  const storedResult = useAppStore((state) => state.devTrackingResult);
  const setDevTrackingResult = useAppStore((state) => state.setDevTrackingResult);
  const storedAnalyses = useAppStore((state) => state.devTrackingAnalyses);
  const setDevTrackingAnalyses = useAppStore((state) => state.setDevTrackingAnalyses);

  const port = backendPort || 8000;

  const ghTokenRef = useRef(null);
  const getGhToken = async () => {
    if (ghTokenRef.current) return ghTokenRef.current;
    try {
      const data = await serverRequest("/auth/github/token", {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      ghTokenRef.current = data.github_oauth_token;
    } catch (_) {}
    return ghTokenRef.current || "";
  };

  const [form, setForm] = useState(DEFAULT_FORM);
  const [connectedRepo, setConnectedRepo] = useState(null);
  const [pullRequests, setPullRequests] = useState([]);
  const [pullLoading, setPullLoading] = useState(false);
  const [pullError, setPullError] = useState("");
  const [branches, setBranches] = useState([]);
  const [branchLoading, setBranchLoading] = useState(false);
  const [branchError, setBranchError] = useState("");
  const [running, setRunning] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [detailLoadingId, setDetailLoadingId] = useState("");
  const [gapDecisionLoadingId, setGapDecisionLoadingId] = useState("");
  const [error, setError] = useState("");
  const [historyError, setHistoryError] = useState("");
  const [result, setResultLocal] = useState(storedResult);
  const [analyses, setAnalysesLocal] = useState(storedAnalyses);
  const [showManualRun, setShowManualRun] = useState(false);

  const setResult = useCallback((val) => {
    setResultLocal(val);
    setDevTrackingResult(val);
  }, [setDevTrackingResult]);

  const setAnalyses = useCallback((val) => {
    setAnalysesLocal(val);
    setDevTrackingAnalyses(val);
  }, [setDevTrackingAnalyses]);

  const data = result?.data || {};
  const state = data?.data || {};
  const timeline = Array.isArray(data?.timeline) ? data.timeline : [];
  const gapReport = Array.isArray(state.gap_report) ? state.gap_report : [];
  const pmReport = state.pm_report || {};
  const approvalTask = state.approval_task || {};
  const llmWarnings = Array.isArray(state.llm_warnings) ? state.llm_warnings : [];
  const pendingAnalyses = analyses.filter((analysis) => String(analysis.approval_status || "").includes("PENDING"));
  const failedAnalyses = analyses.filter((analysis) => {
    const status = String(analysis.analysis_status || analysis.approval_status || "").toUpperCase();
    return status.includes("FAIL") || status.includes("ERROR") || status.includes("BLOCK");
  });
  const firstProblem = useMemo(
    () => timeline.find((item) => ["FAIL", "ERROR", "WARN"].includes(String(item.status || "").toUpperCase())),
    [timeline],
  );

  const panel = isDarkMode
    ? "bg-white/5 border-white/10"
    : "bg-white border-slate-200 shadow-sm";
  const input = isDarkMode
    ? "bg-slate-900/80 border-white/10 text-slate-100 placeholder:text-slate-600"
    : "bg-white border-slate-200 text-slate-900 placeholder:text-slate-400";
  const muted = isDarkMode ? "text-slate-400" : "text-slate-500";

  const updateField = (key, value) => setForm((prev) => ({ ...prev, [key]: value }));

  const applyConnectedRepo = useCallback((repoConfig = connectedRepo) => {
    if (!repoConfig?.owner || !repoConfig?.repo) return;
    // author: xxrin
    // 설정된 GitHub repo를 Advanced 수동 실행 폼에 자동 채워 PM 입력 부담을 줄인다.
    setForm((prev) => ({
      ...prev,
      owner: repoConfig.owner,
      repo: repoConfig.repo,
      base_branch: repoConfig.branch || prev.base_branch || "main",
    }));
  }, [connectedRepo]);

  useEffect(() => {
    if (githubOwner && githubRepo) {
      const repoConfig = { owner: githubOwner, repo: githubRepo, branch: githubBranch || "main", source: "store" };
      setConnectedRepo(repoConfig);
      applyConnectedRepo(repoConfig);
    }
  }, [applyConnectedRepo, githubBranch, githubOwner, githubRepo]);

  useEffect(() => {
    if ((githubOwner && githubRepo) || !authToken || !currentUser?.team_id) return;
    let cancelled = false;
    const fetchTeamRepo = async () => {
      try {
        const json = await serverRequest(`/auth/teams/${currentUser.team_id}`, {
          headers: { Authorization: `Bearer ${authToken}` },
        });
        const fullName = json?.github_repo || "";
        const [owner, repo] = fullName.split("/");
        if (!cancelled && owner && repo) {
          const repoConfig = { owner, repo, branch: "main", source: "team" };
          setConnectedRepo(repoConfig);
          applyConnectedRepo(repoConfig);
        }
      } catch (_) {}
    };
    fetchTeamRepo();
    return () => { cancelled = true; };
  }, [applyConnectedRepo, authToken, currentUser?.team_id, githubOwner, githubRepo]);

  const openAnalysisDetail = async (analysis) => {
    setDetailLoadingId(analysis.id);
    setHistoryError("");
    try {
      const headers = {};
      if (authToken) headers.Authorization = `Bearer ${authToken}`;
      const response = await fetch(`http://127.0.0.1:${port}/api/dev-tracking/analyses/${analysis.id}`, { headers });
      const json = await response.json();
      if (json.status !== "ok") {
        setHistoryError(json.error || "분석 상세 조회에 실패했습니다.");
        return;
      }
      const detail = json.data || {};
      setResult({
        status: "ok",
        data: {
          status: detail.approval_status || detail.analysis_status || "history",
          timeline: detail.timeline || [],
          data: {
            analysis_id: detail.id,
            approval_status: detail.approval_status,
            gap_report: detail.gap_items || [],
            pm_report: detail.pm_report || { summary: detail.pm_report_summary || "" },
            approval_task: { task_id: detail.task_id || "" },
            pr_context: {
              owner: detail.owner,
              repo: detail.repo,
              pr_number: detail.pr_number,
              branch_name: detail.branch_name,
              base_branch: detail.base_branch,
              head_sha: detail.head_sha,
            },
          },
        },
      });
    } catch (detailError) {
      setHistoryError(`분석 상세 조회 실패: ${detailError.message}`);
    } finally {
      setDetailLoadingId("");
    }
  };

  const fetchAnalyses = useCallback(async () => {
    setHistoryLoading(true);
    setHistoryError("");
    try {
      const params = new URLSearchParams();
      if (currentUser?.team_id) params.set("team_id", currentUser.team_id);
      if (form.owner.trim()) params.set("owner", form.owner.trim());
      if (form.repo.trim()) params.set("repo", form.repo.trim());
      params.set("limit", "20");
      const headers = {};
      if (authToken) headers.Authorization = `Bearer ${authToken}`;
      const response = await fetch(`http://127.0.0.1:${port}/api/dev-tracking/analyses?${params}`, { headers });
      const json = await response.json();
      if (json.status === "ok") {
        setAnalyses(Array.isArray(json.data) ? json.data : []);
      } else {
        setHistoryError(json.error || "분석 이력 조회에 실패했습니다.");
      }
    } catch (historyFetchError) {
      setHistoryError(`분석 이력 조회 실패: ${historyFetchError.message}`);
    } finally {
      setHistoryLoading(false);
    }
  }, [authToken, currentUser?.team_id, form.owner, form.repo, port]);

  useEffect(() => {
    fetchAnalyses();
  }, [fetchAnalyses]);

  const applyPullRequest = useCallback((pullRequest) => {
    if (!pullRequest) return;
    // author: xxrin
    // 선택한 PR의 브랜치/head/base 정보를 실행 폼에 자동 반영해 PM이 SHA를 직접 복사하지 않게 한다.
    setForm((prev) => ({
      ...prev,
      owner: connectedRepo?.owner || prev.owner,
      repo: connectedRepo?.repo || prev.repo,
      pr_number: String(pullRequest.number || ""),
      branch_name: pullRequest.head_branch || prev.branch_name,
      base_branch: pullRequest.base_branch || prev.base_branch || "main",
      head_sha: pullRequest.head_sha || prev.head_sha,
    }));
    setPullError("");
  }, [connectedRepo]);

  const applyBranch = useCallback((branch) => {
    if (!branch?.name) return;
    // author: xxrin
    // PR 목록이 없을 때도 GitHub branch 선택만으로 실행 브랜치와 HEAD SHA를 채운다.
    setForm((prev) => ({
      ...prev,
      owner: connectedRepo?.owner || prev.owner,
      repo: connectedRepo?.repo || prev.repo,
      branch_name: branch.name,
      head_sha: branch.sha || prev.head_sha,
    }));
    setBranchError("");
  }, [connectedRepo]);

  const fetchBranches = useCallback(async () => {
    const owner = (connectedRepo?.owner || form.owner || "").trim();
    const repo = (connectedRepo?.repo || form.repo || "").trim();
    if (!owner || !repo) {
      setBranchError("연결 repo 또는 owner/repo 입력값이 필요합니다.");
      return;
    }
    setBranchLoading(true);
    setBranchError("");
    try {
      const json = await serverRequest(
        `/auth/github/branches?owner=${encodeURIComponent(owner)}&repo=${encodeURIComponent(repo)}`,
        { headers: { Authorization: `Bearer ${authToken}` } },
      );
      if (json.status !== "ok") {
        setBranchError(json.error || "브랜치 목록 조회에 실패했습니다.");
        setBranches([]);
        return;
      }
      setBranches(Array.isArray(json.data) ? json.data : []);
    } catch (branchFetchError) {
      setBranchError(`브랜치 목록 조회 실패: ${branchFetchError.message}`);
      setBranches([]);
    } finally {
      setBranchLoading(false);
    }
  }, [authToken, connectedRepo, form.owner, form.repo]);

  const fetchPullRequests = useCallback(async () => {
    const owner = (connectedRepo?.owner || form.owner || "").trim();
    const repo = (connectedRepo?.repo || form.repo || "").trim();
    if (!owner || !repo) {
      setPullError("연결 repo 또는 owner/repo 입력값이 필요합니다.");
      return;
    }
    setPullLoading(true);
    setPullError("");
    try {
      const json = await serverRequest(
        `/auth/github/pulls?owner=${encodeURIComponent(owner)}&repo=${encodeURIComponent(repo)}&state=open&limit=30`,
        { headers: { Authorization: `Bearer ${authToken}` } },
      );
      if (json.status !== "ok") {
        setPullError(json.error || "PR 목록 조회에 실패했습니다.");
        setPullRequests([]);
        return;
      }
      setPullRequests(Array.isArray(json.data) ? json.data : []);
    } catch (pullFetchError) {
      setPullError(`PR 목록 조회 실패: ${pullFetchError.message}`);
      setPullRequests([]);
    } finally {
      setPullLoading(false);
    }
  }, [authToken, connectedRepo, form.owner, form.repo]);

  useEffect(() => {
    if (!connectedRepo?.owner || !connectedRepo?.repo || !authToken) return;
    fetchPullRequests();
    fetchBranches();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authToken, connectedRepo?.owner, connectedRepo?.repo]);

  const runAnalysis = async () => {
    setRunning(true);
    setError("");
    setResult(null);
    try {
      const prNumber = Number(form.pr_number);
      if (!form.owner.trim() || !form.repo.trim() || !prNumber || !form.branch_name.trim() || !form.head_sha.trim()) {
        setError("owner, repo, PR number, branch name, head sha는 필수입니다.");
        setRunning(false);
        return;
      }
      const headers = { "Content-Type": "application/json" };
      if (authToken) headers.Authorization = `Bearer ${authToken}`;
      const response = await fetch(`http://127.0.0.1:${port}/api/dev-tracking/pr`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          repository: {
            owner: form.owner.trim(),
            repo: form.repo.trim(),
          },
          pull_request: {
            pr_number: prNumber,
            branch_name: form.branch_name.trim(),
            base_branch: form.base_branch.trim(),
            head_sha: form.head_sha.trim(),
            created_at: new Date().toISOString(),
            title: `Manual Dev Tracking PR #${prNumber}`,
            description: "Manual Dev Tracking analysis from NAVIGATOR UI.",
          },
          actor: {
            github_id: currentUser?.github_login || currentUser?.github_username || currentUser?.name || "",
            role: "developer",
          },
          source_dir: form.source_dir.trim(),
          api_key: apiKey,
          notify_pr: form.notify_pr,
          use_llm_forensic_profiler: form.use_llm_forensic_profiler,
          use_llm_gap_analyzer: form.use_llm_gap_analyzer,
          use_llm_intent_classifier: form.use_llm_intent_classifier,
          team_id: currentUser?.team_id || "",
          created_by: currentUser?.id || "",
        }),
      });
      const json = await response.json();
      if (json.status !== "ok") {
        setError(json.error || "Dev Tracking 분석 실행에 실패했습니다.");
      } else {
        setResult(json);
        fetchAnalyses();
      }
    } catch (runError) {
      setError(`서버 연결 실패: ${runError.message}`);
    } finally {
      setRunning(false);
    }
  };

  const handleGapItemDecision = async (gap, action) => {
    if (!gap?.id) {
      setError("저장된 GAP 항목만 항목별 승인/거절할 수 있습니다.");
      return;
    }
    setGapDecisionLoadingId(`${gap.id}:${action}`);
    setError("");
    try {
      const headers = { "Content-Type": "application/json" };
      if (authToken) headers.Authorization = `Bearer ${authToken}`;
      const response = await fetch(`http://127.0.0.1:${port}/api/dev-tracking/gaps/${gap.id}/${action}`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          reason: action === "approve"
            ? "PM approved this GAP item as intentional."
            : "PM rejected this GAP item as unintended.",
        }),
      });
      const json = await response.json();
      if (json.status !== "ok") {
        setError(json.error || "GAP 항목 결정 처리에 실패했습니다.");
        return;
      }
      const analysis = json.data?.analysis || {};
      // author: xxrin
      // GAP 항목별 결정 후 상세 카드와 요약 카드가 즉시 같은 analysis 상태를 보도록 local result를 갱신한다.
      setResult((prev) => {
        if (!prev?.data?.data) return prev;
        return {
          ...prev,
          data: {
            ...prev.data,
            status: analysis.approval_status || prev.data.status,
            data: {
              ...prev.data.data,
              approval_status: analysis.approval_status || prev.data.data.approval_status,
              gap_report: analysis.gap_items || prev.data.data.gap_report,
              pm_report: analysis.pm_report || prev.data.data.pm_report,
            },
          },
        };
      });
      fetchAnalyses();
    } catch (decisionError) {
      setError(`GAP 항목 결정 처리 실패: ${decisionError.message}`);
    } finally {
      setGapDecisionLoadingId("");
    }
  };

  const historyPanel = (
    <div className={`rounded-2xl border p-4 space-y-3 ${panel}`}>
      <div className="flex items-center justify-between gap-2">
        <h3 className={`text-sm font-black ${isDarkMode ? "text-white" : "text-slate-900"}`}>Recent Analyses</h3>
        <button
          type="button"
          onClick={fetchAnalyses}
          disabled={historyLoading}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-bold ${isDarkMode ? "bg-white/5 border-white/10" : "bg-slate-50 border-slate-200"}`}
        >
          {historyLoading ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
          새로고침
        </button>
      </div>
      {historyError && <p className="text-xs text-red-400">{historyError}</p>}
      <div className="space-y-2 max-h-80 overflow-y-auto custom-scrollbar pr-1">
        {analyses.length === 0 && !historyLoading ? (
          <p className={`text-xs ${muted}`}>저장된 분석 이력이 없습니다.</p>
        ) : analyses.map((analysis) => (
          <button
            key={analysis.id}
            type="button"
            onClick={() => openAnalysisDetail(analysis)}
            className={`w-full text-left rounded-xl border p-3 transition-all ${isDarkMode ? "bg-black/20 border-white/10 hover:bg-white/10" : "bg-slate-50 border-slate-200 hover:bg-slate-100"}`}
          >
            <div className="flex items-center justify-between gap-2">
              <span className={`text-xs font-black ${isDarkMode ? "text-slate-100" : "text-slate-800"}`}>
                PR #{analysis.pr_number} · {analysis.branch_name || "-"}
              </span>
              <span className={`px-2 py-0.5 rounded border text-[10px] font-bold ${statusTone(analysis.approval_status || analysis.analysis_status)}`}>
                {detailLoadingId === analysis.id ? "LOADING" : (analysis.approval_status || analysis.analysis_status || "-")}
              </span>
            </div>
            <div className={`mt-1 text-[11px] ${muted}`}>
              {analysis.owner}/{analysis.repo} · GAP {analysis.gap_count || 0}
              {analysis.high_gap_count ? ` · HIGH ${analysis.high_gap_count}` : ""}
            </div>
            <div className={`mt-1 text-[10px] font-mono break-all ${muted}`}>
              {analysis.head_sha || "-"}
            </div>
            {analysis.task_id && (
              <div className={`mt-1 text-[10px] ${muted}`}>task: {analysis.task_id}</div>
            )}
          </button>
        ))}
      </div>
    </div>
  );

  return (
    <div className={`h-full p-6 space-y-5 ${isDarkMode ? "text-slate-300" : "text-slate-800"}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className={`text-2xl font-black tracking-tight flex items-center gap-2 ${isDarkMode ? "text-white" : "text-slate-900"}`}>
            <GitPullRequest size={22} /> Dev Tracking
          </h2>
          <p className={`text-sm mt-1 ${muted}`}>Webhook으로 들어온 PR 분석 상태와 PM 승인 대기 GAP을 확인합니다.</p>
        </div>
        <button
          type="button"
          onClick={() => { setForm(DEFAULT_FORM); setResult(null); setError(""); }}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold border transition-all ${panel}`}
        >
          <RefreshCw size={14} /> 초기화
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {[
          ["Recent Analyses", analyses.length, "저장된 PR 분석"],
          ["Pending Approval", pendingAnalyses.length, "PM 판단 대기"],
          ["Failed / Blocked", failedAnalyses.length, "확인 필요"],
        ].map(([label, value, caption]) => (
          <div key={label} className={`rounded-2xl border p-4 ${panel}`}>
            <div className={`text-xs font-bold uppercase tracking-wider ${muted}`}>{label}</div>
            <div className={`text-3xl font-black mt-2 ${isDarkMode ? "text-white" : "text-slate-900"}`}>{value}</div>
            <div className={`text-xs mt-1 ${muted}`}>{caption}</div>
          </div>
        ))}
      </div>

      <div className={`rounded-2xl border ${panel}`}>
        <button
          type="button"
          onClick={() => setShowManualRun((value) => !value)}
          className="w-full flex items-center justify-between gap-3 p-4 text-left"
        >
          <div>
            <div className={`text-sm font-black ${isDarkMode ? "text-white" : "text-slate-900"}`}>Advanced Manual Run</div>
            <div className={`text-xs mt-1 ${muted}`}>
              {connectedRepo
                ? `Connected repo: ${connectedRepo.owner}/${connectedRepo.repo}`
                : "Webhook/repo cache가 없을 때만 PR 분석을 수동 실행합니다."}
            </div>
          </div>
          {showManualRun ? <ChevronDown size={16} className="opacity-60" /> : <ChevronRight size={16} className="opacity-60" />}
        </button>

        {showManualRun && (
          <div className={`border-t p-4 space-y-4 ${isDarkMode ? "border-white/10" : "border-slate-200"}`}>
            <div className={`rounded-xl border p-3 text-xs ${isDarkMode ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-100" : "bg-emerald-50 border-emerald-200 text-emerald-800"}`}>
              Webhook이 연결된 저장소는 PR 이벤트에서 owner/repo/branch/head SHA를 자동 추출합니다. 이 폼은 수동 재현과 디버깅용입니다.
              {connectedRepo && (
                <button
                  type="button"
                  onClick={() => applyConnectedRepo()}
                  className={`ml-3 px-2 py-1 rounded-lg text-[11px] font-bold ${isDarkMode ? "bg-white/10 text-white" : "bg-white text-emerald-800 border border-emerald-200"}`}
                >
                  연결 repo 사용
                </button>
              )}
            </div>
            <div className={`rounded-xl border p-3 space-y-3 ${isDarkMode ? "bg-black/20 border-white/10" : "bg-slate-50 border-slate-200"}`}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <div className={`text-xs font-black ${isDarkMode ? "text-white" : "text-slate-900"}`}>Open PR 자동 선택</div>
                  <div className={`text-[11px] mt-0.5 ${muted}`}>
                    {connectedRepo ? `${connectedRepo.owner}/${connectedRepo.repo}` : "입력된 owner/repo"} 기준으로 브랜치와 HEAD SHA를 불러옵니다.
                  </div>
                </div>
                <button
                  type="button"
                  onClick={fetchPullRequests}
                  disabled={pullLoading}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-bold ${isDarkMode ? "bg-white/5 border-white/10" : "bg-white border-slate-200"}`}
                >
                  {pullLoading ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
                  PR 불러오기
                </button>
              </div>
              {pullError && <p className="text-xs text-red-400">{pullError}</p>}
              {pullRequests.length > 0 && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-2 max-h-56 overflow-y-auto custom-scrollbar pr-1">
                  {pullRequests.map((pullRequest) => (
                    <button
                      key={pullRequest.number}
                      type="button"
                      onClick={() => applyPullRequest(pullRequest)}
                      className={`text-left rounded-xl border p-3 transition-all ${String(form.pr_number) === String(pullRequest.number) ? "border-emerald-500/60 bg-emerald-500/10" : (isDarkMode ? "border-white/10 bg-white/5 hover:bg-white/10" : "border-slate-200 bg-white hover:bg-slate-100")}`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className={`text-xs font-black truncate ${isDarkMode ? "text-slate-100" : "text-slate-900"}`}>
                          #{pullRequest.number} {pullRequest.title || "Untitled PR"}
                        </span>
                        <span className={`px-2 py-0.5 rounded border text-[10px] font-bold ${statusTone(pullRequest.state)}`}>
                          {pullRequest.state || "open"}
                        </span>
                      </div>
                      <div className={`mt-1 text-[11px] ${muted}`}>
                        {pullRequest.head_branch || "-"} → {pullRequest.base_branch || "-"}
                      </div>
                      <div className={`mt-1 text-[10px] font-mono break-all ${muted}`}>
                        {pullRequest.head_sha || "-"}
                      </div>
                    </button>
                  ))}
                </div>
              )}
              {!pullLoading && !pullError && pullRequests.length === 0 && (
                <p className={`text-xs ${muted}`}>열린 PR을 불러오면 실행값을 선택할 수 있습니다.</p>
              )}
            </div>
            <div className={`rounded-xl border p-3 space-y-3 ${isDarkMode ? "bg-black/20 border-white/10" : "bg-slate-50 border-slate-200"}`}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <div className={`text-xs font-black ${isDarkMode ? "text-white" : "text-slate-900"}`}>Branch 자동 선택</div>
                  <div className={`text-[11px] mt-0.5 ${muted}`}>PR 없이 브랜치만 재분석할 때 실행 브랜치와 HEAD SHA를 채웁니다.</div>
                </div>
                <button
                  type="button"
                  onClick={fetchBranches}
                  disabled={branchLoading}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-bold ${isDarkMode ? "bg-white/5 border-white/10" : "bg-white border-slate-200"}`}
                >
                  {branchLoading ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
                  브랜치 불러오기
                </button>
              </div>
              {branchError && <p className="text-xs text-red-400">{branchError}</p>}
              {branches.length > 0 && (
                <div className="flex flex-wrap gap-2 max-h-32 overflow-y-auto custom-scrollbar pr-1">
                  {branches.map((branch) => (
                    <button
                      key={branch.name}
                      type="button"
                      onClick={() => applyBranch(branch)}
                      className={`px-3 py-1.5 rounded-lg border text-xs font-bold ${form.branch_name === branch.name ? "border-emerald-500/60 bg-emerald-500/10 text-emerald-300" : (isDarkMode ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10" : "border-slate-200 bg-white text-slate-700 hover:bg-slate-100")}`}
                    >
                      {branch.name}
                    </button>
                  ))}
                </div>
              )}
              {!branchLoading && !branchError && branches.length === 0 && (
                <p className={`text-xs ${muted}`}>브랜치를 불러오면 실행 브랜치를 선택할 수 있습니다.</p>
              )}
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <label className="space-y-1.5 text-xs font-bold">
                <span className={muted}>Owner *</span>
                <input className={`w-full px-3 py-2 rounded-lg border outline-none ${input}`} value={form.owner} onChange={(e) => updateField("owner", e.target.value)} placeholder="org" />
              </label>
              <label className="space-y-1.5 text-xs font-bold">
                <span className={muted}>Repo *</span>
                <input className={`w-full px-3 py-2 rounded-lg border outline-none ${input}`} value={form.repo} onChange={(e) => updateField("repo", e.target.value)} placeholder="navigator" />
              </label>
              <label className="space-y-1.5 text-xs font-bold">
                <span className={muted}>PR Number *</span>
                <input className={`w-full px-3 py-2 rounded-lg border outline-none ${input}`} value={form.pr_number} onChange={(e) => updateField("pr_number", e.target.value)} placeholder="12" inputMode="numeric" />
              </label>
              <label className="space-y-1.5 text-xs font-bold">
                <span className={muted}>Branch *</span>
                <input className={`w-full px-3 py-2 rounded-lg border outline-none ${input}`} value={form.branch_name} onChange={(e) => updateField("branch_name", e.target.value)} placeholder="feature/dev-tracking" />
              </label>
              <label className="space-y-1.5 text-xs font-bold">
                <span className={muted}>Base Branch</span>
                <input className={`w-full px-3 py-2 rounded-lg border outline-none ${input}`} value={form.base_branch} onChange={(e) => updateField("base_branch", e.target.value)} placeholder="main" />
              </label>
              <label className="space-y-1.5 text-xs font-bold">
                <span className={muted}>Head SHA *</span>
                <input className={`w-full px-3 py-2 rounded-lg border outline-none font-mono ${input}`} value={form.head_sha} onChange={(e) => updateField("head_sha", e.target.value)} placeholder="abc123" />
              </label>
              <label className="space-y-1.5 text-xs font-bold md:col-span-3">
                <span className={muted}>Source Dir Override</span>
                <input className={`w-full px-3 py-2 rounded-lg border outline-none font-mono ${input}`} value={form.source_dir} onChange={(e) => updateField("source_dir", e.target.value)} placeholder="비워두면 backend repo cache를 사용합니다." />
              </label>
            </div>

            <div className="flex flex-wrap gap-3">
              {[
                ["notify_pr", "PR 코멘트 작성"],
                ["use_llm_forensic_profiler", "LLM 구현 분석"],
                ["use_llm_gap_analyzer", "LLM GAP 분석"],
                ["use_llm_intent_classifier", "LLM 의도 분류"],
              ].map(([key, label]) => (
                <label key={key} className={`flex items-center gap-2 px-3 py-2 rounded-xl border text-xs font-bold ${isDarkMode ? "bg-black/20 border-white/10" : "bg-slate-50 border-slate-200"}`}>
                  <input type="checkbox" checked={Boolean(form[key])} onChange={(e) => updateField(key, e.target.checked)} />
                  {label}
                </label>
              ))}
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={runAnalysis}
                disabled={running}
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-bold bg-emerald-600 hover:bg-emerald-500 disabled:opacity-60 text-white transition-all"
              >
                {running ? <Loader2 size={15} className="animate-spin" /> : <Play size={15} />}
                분석 실행
              </button>
              {!authToken && <span className="text-xs text-amber-400">인증 토큰이 없으면 팀/PM 권한 흐름이 제한될 수 있습니다.</span>}
            </div>
          </div>
        )}
      </div>

      {error && (
        <div className={`rounded-xl border p-3 text-sm ${isDarkMode ? "bg-red-500/10 border-red-500/25 text-red-300" : "bg-red-50 border-red-200 text-red-700"}`}>
          {error}
        </div>
      )}

      {!result && (
        <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_360px] gap-5">
          <div className={`rounded-2xl border p-4 flex items-center justify-center min-h-56 ${panel}`}>
            <p className={`text-sm text-center ${muted}`}>PR 정보를 입력해 분석을 실행하거나, 최근 분석 이력을 선택하세요.</p>
          </div>
          {historyPanel}
        </div>
      )}

      {result && (
        <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_360px] gap-5">
          <div className={`rounded-2xl border p-4 space-y-3 ${panel}`}>
            <div className="flex items-center justify-between gap-3">
              <h3 className={`text-sm font-black ${isDarkMode ? "text-white" : "text-slate-900"}`}>Pipeline Timeline</h3>
              <span className={`px-2 py-1 rounded-lg border text-xs font-bold ${statusTone(data.status)}`}>{data.status || "unknown"}</span>
            </div>
            {firstProblem && (
              <div className={`rounded-xl border p-3 text-xs ${isDarkMode ? "bg-amber-500/10 border-amber-500/20 text-amber-100" : "bg-amber-50 border-amber-200 text-amber-800"}`}>
                먼저 확인할 노드: <strong>{firstProblem.node}</strong> ({firstProblem.status}) {firstProblem.error_type || ""}
              </div>
            )}
            <div className="space-y-2">
              {timeline.length === 0 ? (
                <p className={`text-sm ${muted}`}>타임라인이 없습니다.</p>
              ) : timeline.map((item, index) => {
                const Icon = nodeIcon(item.status);
                return (
                  <div key={`${item.node}-${index}`} className={`rounded-xl border p-3 flex items-start gap-3 ${isDarkMode ? "bg-black/20 border-white/10" : "bg-slate-50 border-slate-200"}`}>
                    <Icon size={16} className={statusTone(item.status).split(" ")[0]} />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`text-sm font-bold ${isDarkMode ? "text-slate-100" : "text-slate-800"}`}>{item.node}</span>
                        <span className={`px-2 py-0.5 rounded border text-[11px] font-bold ${statusTone(item.status)}`}>{item.status || "-"}</span>
                      </div>
                      <p className={`text-xs mt-1 ${muted}`}>next: {item.next_action || "-"}</p>
                      {item.error_type && <p className="text-xs mt-1 text-red-400">error: {item.error_type}</p>}
                    </div>
                  </div>
                );
              })}
            </div>
            {gapReport.length > 0 && (
              <div className="pt-3 border-t border-white/10 space-y-2">
                <h3 className={`text-sm font-black ${isDarkMode ? "text-white" : "text-slate-900"}`}>GAP Details</h3>
                {gapReport.map((gap, index) => (
                  <div key={gap.gap_id || gap.id || index} className={`rounded-xl border p-3 ${isDarkMode ? "bg-black/20 border-white/10" : "bg-slate-50 border-slate-200"}`}>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={`text-[11px] px-2 py-0.5 rounded font-mono ${isDarkMode ? "bg-white/10 text-slate-200" : "bg-white border border-slate-200 text-slate-700"}`}>
                        {gap.gap_id || `GAP_${index + 1}`}
                      </span>
                      <span className={`text-[11px] px-2 py-0.5 rounded border font-bold ${statusTone(gap.severity)}`}>
                        {gap.severity || "UNKNOWN"}
                      </span>
                      <span className={`text-[11px] px-2 py-0.5 rounded ${isDarkMode ? "bg-white/10 text-slate-300" : "bg-slate-200 text-slate-700"}`}>
                        {gap.type || "-"}
                      </span>
                      {gap.approval_status && (
                        <span className={`text-[11px] px-2 py-0.5 rounded border font-bold ${statusTone(gap.approval_status)}`}>
                          {gap.approval_status}
                        </span>
                      )}
                    </div>
                    <p className={`mt-2 text-xs leading-relaxed ${isDarkMode ? "text-slate-200" : "text-slate-800"}`}>
                      {gap.description || "설명 없음"}
                    </p>
                    <div className={`grid grid-cols-1 md:grid-cols-2 gap-2 mt-2 text-[11px] ${muted}`}>
                      <span><strong>Spec:</strong> {gap.spec_target || "-"}</span>
                      <span><strong>Implementation:</strong> {gap.implementation_target || "-"}</span>
                      <span><strong>Intent:</strong> {gap.intent || "-"}</span>
                      <span><strong>Action:</strong> {gap.recommended_action || "-"}</span>
                      {gap.approved_by && <span><strong>Reviewed:</strong> {gap.approved_by}</span>}
                      {gap.approved_at && <span><strong>At:</strong> {gap.approved_at}</span>}
                    </div>
                    {gap.id && (
                      <div className="flex flex-wrap gap-2 mt-3">
                        <button
                          type="button"
                          onClick={() => handleGapItemDecision(gap, "approve")}
                          disabled={Boolean(gapDecisionLoadingId)}
                          className="px-3 py-1.5 rounded-lg text-[11px] font-bold bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white"
                        >
                          {gapDecisionLoadingId === `${gap.id}:approve` ? "처리 중" : "항목 승인"}
                        </button>
                        <button
                          type="button"
                          onClick={() => handleGapItemDecision(gap, "reject")}
                          disabled={Boolean(gapDecisionLoadingId)}
                          className="px-3 py-1.5 rounded-lg text-[11px] font-bold bg-red-600 hover:bg-red-500 disabled:opacity-50 text-white"
                        >
                          {gapDecisionLoadingId === `${gap.id}:reject` ? "처리 중" : "항목 거절"}
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="space-y-5">
            {historyPanel}

            <div className={`rounded-2xl border p-4 space-y-3 ${panel}`}>
              <h3 className={`text-sm font-black flex items-center gap-2 ${isDarkMode ? "text-white" : "text-slate-900"}`}>
                <ShieldCheck size={16} /> Summary
              </h3>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className={`rounded-xl p-3 ${isDarkMode ? "bg-black/20" : "bg-slate-50"}`}>
                  <div className={muted}>GAP</div>
                  <div className="text-xl font-black">{gapReport.length}</div>
                </div>
                <div className={`rounded-xl p-3 ${isDarkMode ? "bg-black/20" : "bg-slate-50"}`}>
                  <div className={muted}>Approval</div>
                  <div className="text-xs font-black break-all">{state.approval_status || "-"}</div>
                </div>
              </div>
              {pmReport.summary && <p className={`text-xs leading-relaxed ${muted}`}>{pmReport.summary}</p>}
              {approvalTask.task_id && (
                <div className={`rounded-xl border p-3 text-xs ${isDarkMode ? "border-white/10 bg-white/5" : "border-slate-200 bg-slate-50"}`}>
                  <div className="font-bold">Approval Task</div>
                  <div className="font-mono mt-1 break-all">{approvalTask.task_id}</div>
                </div>
              )}
            </div>

            {llmWarnings.length > 0 && (
              <div className={`rounded-2xl border p-4 space-y-2 ${isDarkMode ? "bg-yellow-500/10 border-yellow-500/25 text-yellow-100" : "bg-yellow-50 border-yellow-200 text-yellow-900"}`}>
                <h3 className="text-sm font-black flex items-center gap-2"><AlertTriangle size={16} /> LLM Warnings</h3>
                {llmWarnings.map((warning, index) => (
                  <p key={`${warning.node || "warning"}-${index}`} className="text-xs leading-relaxed">
                    <strong>{warning.node || "llm"}:</strong> {warning.message || warning.llm_error_message || "Fallback analysis was used."}
                  </p>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
