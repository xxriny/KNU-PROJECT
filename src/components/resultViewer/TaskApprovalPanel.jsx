import React, { useState, useEffect, useCallback } from "react";
import useAppStore from "../../store/useAppStore";
import {
  ClipboardList, Check, X, Clock, Loader2, RefreshCw,
  ChevronDown, ChevronRight, AlertTriangle, CheckCircle,
  XCircle, Plus, Trash2, Sparkles, Users, GitPullRequest,
  CircleDot, Inbox,
} from "lucide-react";

const STATUS_CONFIG = {
  unassigned:       { label: "미할당",     color: "text-slate-400",   bg: "bg-slate-500/10",    border: "border-slate-500/20",   Icon: Inbox },
  pending_approval: { label: "승인대기중", color: "text-yellow-400",  bg: "bg-yellow-500/10",   border: "border-yellow-500/30",  Icon: Clock },
  in_progress:      { label: "진행중",     color: "text-blue-400",    bg: "bg-blue-500/10",     border: "border-blue-500/30",    Icon: CircleDot },
  pr_pending:       { label: "PR대기중",   color: "text-violet-400",  bg: "bg-violet-500/10",   border: "border-violet-500/30",  Icon: GitPullRequest },
  completed:        { label: "완료",       color: "text-emerald-400", bg: "bg-emerald-500/10",  border: "border-emerald-500/30", Icon: CheckCircle },
  rejected:         { label: "거절",       color: "text-red-400",     bg: "bg-red-500/10",      border: "border-red-500/30",     Icon: XCircle },
};

const FILTER_TABS = ["all", "unassigned", "pending_approval", "in_progress", "pr_pending", "completed", "rejected"];

const TASK_TYPE_LABEL = {
  feature:       "기능 개발",
  bugfix:        "버그 수정",
  refactor:      "리팩토링",
  test:          "테스트",
  infra:         "인프라/DevOps",
  doc_sync:      "문서 동기화",
  publish_docs:  "설계 문서 퍼블리시",
  verify_sa:     "SA 검증",
};

const EFFORT_LABEL = { S: "S (2h↓)", M: "M (2~8h)", L: "L (1~3d)", XL: "XL (3d↑)" };

const AREA_LABEL = {
  backend:   "백엔드",
  frontend:  "프론트엔드",
  fullstack: "풀스택",
  devops:    "DevOps",
};

const TASK_TYPES = ["feature", "bugfix", "refactor", "test", "infra", "doc_sync"];
const AREAS = ["backend", "frontend", "fullstack", "devops"];

// 역할별 볼 수 있는 area 필터
const ROLE_AREAS = {
  backend:  ["backend", "fullstack"],
  frontend: ["frontend", "fullstack"],
  devops:   ["devops"],
  engineer: null, // fullstack — 모두 볼 수 있음
  pm:       null, // 모두 볼 수 있음
};

export default function TaskApprovalPanel() {
  const isDarkMode  = useAppStore((s) => s.isDarkMode);
  const userRole    = useAppStore((s) => s.userRole);
  const currentUser = useAppStore((s) => s.currentUser);
  const backendPort = useAppStore((s) => s.backendPort);
  const authToken   = useAppStore((s) => s.authToken);
  const resultData  = useAppStore((s) => s.resultData);
  const apiKey      = useAppStore((s) => s.apiKey) || "";

  const port    = backendPort || 8000;
  const isPM    = userRole === "pm";
  const userId  = currentUser?.id || "";
  const teamId  = currentUser?.team_id || "";
  const runId   = resultData?.run_id || "";

  const [tasks, setTasks]               = useState([]);
  const [loading, setLoading]           = useState(false);
  const [error, setError]               = useState("");
  const [expandedIds, setExpandedIds]   = useState(() => new Set());
  const [filterStatus, setFilterStatus] = useState("all");
  const [teamMembers, setTeamMembers]   = useState([]);

  // 커스텀 태스크 생성 폼
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [createForm, setCreateForm] = useState({
    task_type: "feature", title: "", description: "", area: "backend", assignee: "",
  });
  const [createLoading, setCreateLoading] = useState(false);
  const [createMsg, setCreateMsg]         = useState("");

  // AI 태스크 생성
  const [genLoading, setGenLoading] = useState(false);
  const [genMsg, setGenMsg]         = useState("");

  // 배분
  const [distLoading, setDistLoading] = useState(false);
  const [distMsg, setDistMsg]         = useState("");

  const fetchTeamMembers = useCallback(async () => {
    if (!authToken) return;
    try {
      const res = await fetch(`http://127.0.0.1:${port}/api/teams/me/members`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      const data = await res.json();
      setTeamMembers(data.members || []);
    } catch (_) {}
  }, [port, authToken]);

  useEffect(() => { fetchTeamMembers(); }, [fetchTeamMembers]);

  const fetchTasks = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const params = new URLSearchParams();
      if (filterStatus !== "all") params.set("status", filterStatus);
      if (teamId) params.set("team_id", teamId);
      const query = params.toString() ? `?${params}` : "";
      const res  = await fetch(`http://127.0.0.1:${port}/api/tasks${query}`);
      const json = await res.json();
      if (json.status === "ok") setTasks(json.data);
      else setError(json.error || "조회 실패");
    } catch (e) { setError("서버 연결 실패: " + e.message); }
    finally { setLoading(false); }
  }, [port, filterStatus, teamId]);

  useEffect(() => { fetchTasks(); }, [fetchTasks]);

  // 상태 전환
  const handleAction = async (taskId, newStatus) => {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/api/tasks/${taskId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus, reviewed_by: userId }),
      });
      const json = await res.json();
      if (json.status === "ok") setTasks((prev) => prev.map((t) => t.id === taskId ? json.data : t));
      else setError(json.error || "업데이트 실패");
    } catch (e) { setError("서버 연결 실패: " + e.message); }
  };

  // AI 태스크 자동 생성
  const handleGenerateTasks = async () => {
    if (!runId) { setGenMsg("분석 결과(run_id)가 없습니다. 파이프라인을 먼저 실행하세요."); return; }
    if (!teamId) { setGenMsg("팀 정보가 없습니다."); return; }
    setGenLoading(true); setGenMsg("");
    try {
      const res = await fetch(`http://127.0.0.1:${port}/api/agile/generate-tasks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ run_id: runId, team_id: teamId, api_key: apiKey, created_by: userId }),
      });
      const json = await res.json();
      if (json.status === "ok") {
        const d = json.data;
        setGenMsg(`생성 완료: ${d.created}개 추가, ${d.skipped}개 스킵`);
        fetchTasks();
      } else {
        setGenMsg("실패: " + (json.error || "unknown"));
      }
    } catch (e) { setGenMsg("연결 실패: " + e.message); }
    finally { setGenLoading(false); }
  };

  // 팀 배분
  const handleDistribute = async () => {
    if (!teamId) { setDistMsg("팀 정보가 없습니다."); return; }
    setDistLoading(true); setDistMsg("");
    try {
      const res = await fetch(`http://127.0.0.1:${port}/api/agile/distribute-tasks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ team_id: teamId, api_key: apiKey, distributed_by: userId }),
      });
      const json = await res.json();
      if (json.status === "ok") {
        const d = json.data;
        setDistMsg(d.assigned > 0
          ? `배분 완료: ${d.assigned}개 태스크 배분됨`
          : (d.message || "배분할 태스크 없음"));
        fetchTasks();
      } else {
        setDistMsg("실패: " + (json.error || "unknown"));
      }
    } catch (e) { setDistMsg("연결 실패: " + e.message); }
    finally { setDistLoading(false); }
  };

  // 커스텀 태스크 생성
  const handleCreateCustomTask = async () => {
    if (!createForm.title.trim()) { setCreateMsg("제목을 입력하세요."); return; }
    setCreateLoading(true); setCreateMsg("");
    try {
      const res = await fetch(`http://127.0.0.1:${port}/api/tasks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...createForm, created_by: userId, team_id: teamId }),
      });
      const json = await res.json();
      if (json.status === "ok") {
        setCreateMsg("태스크가 생성되었습니다.");
        setCreateForm({ task_type: "feature", title: "", description: "", area: "backend", assignee: "" });
        setShowCreateForm(false);
        fetchTasks();
      } else {
        setCreateMsg("실패: " + (json.error || "unknown"));
      }
    } catch (e) { setCreateMsg("연결 실패: " + e.message); }
    finally { setCreateLoading(false); }
  };

  const handleDelete = async (taskId) => {
    try {
      const res  = await fetch(`http://127.0.0.1:${port}/api/tasks/${taskId}`, { method: "DELETE" });
      const json = await res.json();
      if (json.status === "ok") setTasks((prev) => prev.filter((t) => t.id !== taskId));
      else setError(json.error || "삭제 실패");
    } catch (e) { setError("서버 연결 실패: " + e.message); }
  };

  const toggleExpand = (id) =>
    setExpandedIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const roleAreaFilter = ROLE_AREAS[userRole] ?? null;
  const visibleTasks = tasks
    .filter((t) => filterStatus === "all" || t.status === filterStatus)
    .filter((t) => {
      if (!roleAreaFilter) return true;
      if (!t.area) return false;
      return roleAreaFilter.includes(t.area);
    });

  const countOf = (s) => tasks.filter((t) => t.status === s).length;

  const base = isDarkMode
    ? "bg-white/5 border-white/10 hover:bg-white/10"
    : "bg-slate-100 border-slate-200 hover:bg-slate-200";

  return (
    <div className={`h-full flex flex-col p-6 space-y-5 ${isDarkMode ? "text-slate-300" : "text-slate-800"}`}>
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className={`text-2xl font-black tracking-tight flex items-center gap-2 ${isDarkMode ? "text-white" : "text-slate-900"}`}>
            <ClipboardList size={22} /> 태스크 관리
          </h2>
          <p className="text-sm opacity-60 mt-1">
            {isPM ? "AI가 생성한 태스크를 배분하고 승인·거절하세요." : "담당 태스크를 확인하고 상태를 업데이트하세요."}
          </p>
        </div>
        <button
          onClick={fetchTasks}
          disabled={loading}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-bold border transition-all ${base}`}
        >
          {loading ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
          새로고침
        </button>
      </div>

      {/* PM Quick Actions */}
      {isPM && (
        <div className={`p-4 rounded-2xl border space-y-3 ${isDarkMode ? "bg-white/5 border-white/10" : "bg-white border-slate-200 shadow-sm"}`}>
          <p className="text-xs font-bold uppercase tracking-wider opacity-60">AI 태스크 관리</p>

          {/* 1행: AI 생성 + 배분 */}
          <div className="flex flex-wrap gap-2">
            <button
              onClick={handleGenerateTasks}
              disabled={genLoading || !runId}
              title={!runId ? "파이프라인 실행 후 사용 가능" : ""}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all ${
                runId
                  ? "bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-500/10"
                  : isDarkMode ? "bg-white/5 text-slate-500 cursor-not-allowed" : "bg-slate-100 text-slate-400 cursor-not-allowed"
              }`}
            >
              {genLoading ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />}
              AI 태스크 생성
            </button>
            <button
              onClick={handleDistribute}
              disabled={distLoading}
              className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold bg-violet-600 hover:bg-violet-500 text-white shadow-lg shadow-violet-500/10 transition-all"
            >
              {distLoading ? <Loader2 size={12} className="animate-spin" /> : <Users size={12} />}
              팀 배분
            </button>
            <button
              onClick={() => { setShowCreateForm((v) => !v); setCreateMsg(""); }}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold border transition-all ${base}`}
            >
              <Plus size={12} /> 직접 생성
            </button>
          </div>

          {/* 피드백 메시지 */}
          {genMsg && (
            <p className={`text-xs ${genMsg.startsWith("실패") || genMsg.startsWith("연결") || genMsg.includes("없습니다") ? "text-red-400" : "text-emerald-400"}`}>
              {genMsg}
            </p>
          )}
          {distMsg && (
            <p className={`text-xs ${distMsg.startsWith("실패") || distMsg.startsWith("연결") ? "text-red-400" : "text-blue-400"}`}>
              {distMsg}
            </p>
          )}

          {/* 커스텀 태스크 생성 폼 */}
          {showCreateForm && (
            <div className={`mt-1 p-4 rounded-xl border space-y-3 ${isDarkMode ? "bg-black/20 border-white/10" : "bg-slate-50 border-slate-200"}`}>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold opacity-60 mb-1">태스크 유형</label>
                  <select
                    value={createForm.task_type}
                    onChange={(e) => setCreateForm((f) => ({ ...f, task_type: e.target.value }))}
                    style={{ colorScheme: isDarkMode ? "dark" : "light" }}
                    className={`w-full px-3 py-2 rounded-lg text-xs font-semibold border outline-none ${isDarkMode ? "bg-slate-800 border-white/10 text-slate-100" : "bg-white border-slate-200 text-slate-800"}`}
                  >
                    {TASK_TYPES.map((t) => <option key={t} value={t}>{TASK_TYPE_LABEL[t] || t}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-bold opacity-60 mb-1">담당 영역</label>
                  <select
                    value={createForm.area}
                    onChange={(e) => setCreateForm((f) => ({ ...f, area: e.target.value }))}
                    style={{ colorScheme: isDarkMode ? "dark" : "light" }}
                    className={`w-full px-3 py-2 rounded-lg text-xs font-semibold border outline-none ${isDarkMode ? "bg-slate-800 border-white/10 text-slate-100" : "bg-white border-slate-200 text-slate-800"}`}
                  >
                    {AREAS.map((a) => <option key={a} value={a}>{AREA_LABEL[a] || a}</option>)}
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-xs font-bold opacity-60 mb-1">제목 *</label>
                <input
                  type="text"
                  value={createForm.title}
                  onChange={(e) => setCreateForm((f) => ({ ...f, title: e.target.value }))}
                  placeholder="태스크 제목을 입력하세요"
                  className={`w-full px-3 py-2 rounded-lg text-xs border outline-none ${isDarkMode ? "bg-white/5 border-white/10 text-white placeholder:text-slate-500" : "bg-white border-slate-200 text-slate-800"}`}
                />
              </div>
              <div>
                <label className="block text-xs font-bold opacity-60 mb-1">설명</label>
                <textarea
                  value={createForm.description}
                  onChange={(e) => setCreateForm((f) => ({ ...f, description: e.target.value }))}
                  placeholder="태스크에 대한 상세 설명"
                  rows={2}
                  className={`w-full px-3 py-2 rounded-lg text-xs border outline-none resize-none ${isDarkMode ? "bg-white/5 border-white/10 text-white placeholder:text-slate-500" : "bg-white border-slate-200 text-slate-800"}`}
                />
              </div>
              <div>
                <label className="block text-xs font-bold opacity-60 mb-1">담당자</label>
                <select
                  value={createForm.assignee}
                  onChange={(e) => setCreateForm((f) => ({ ...f, assignee: e.target.value }))}
                  style={{ colorScheme: isDarkMode ? "dark" : "light" }}
                  className={`w-full px-3 py-2 rounded-lg text-xs font-semibold border outline-none ${isDarkMode ? "bg-slate-800 border-white/10 text-slate-100" : "bg-white border-slate-200 text-slate-800"}`}
                >
                  <option value="">미할당</option>
                  {teamMembers.filter((m) => m.role !== "pm").map((m) => (
                    <option key={m.id} value={m.name}>
                      {m.name} — {m.role}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex gap-2 pt-1">
                <button
                  onClick={handleCreateCustomTask}
                  disabled={createLoading}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold bg-violet-600 hover:bg-violet-500 text-white transition-all"
                >
                  {createLoading ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} />}
                  생성
                </button>
                <button
                  onClick={() => { setShowCreateForm(false); setCreateMsg(""); }}
                  className={`px-4 py-2 rounded-xl text-xs font-bold border transition-all ${base}`}
                >
                  취소
                </button>
              </div>
              {createMsg && (
                <p className={`text-xs ${createMsg.startsWith("실패") || createMsg.startsWith("연결") ? "text-red-400" : "text-emerald-400"}`}>
                  {createMsg}
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {/* Filter Tabs */}
      <div className="flex gap-1.5 flex-wrap">
        {FILTER_TABS.map((s) => (
          <button
            key={s}
            onClick={() => setFilterStatus(s)}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
              filterStatus === s
                ? isDarkMode ? "bg-white/15 text-white" : "bg-slate-800 text-white"
                : isDarkMode ? "bg-white/5 text-slate-400 hover:text-slate-200" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            {s === "all" ? "전체" : STATUS_CONFIG[s]?.label || s}
            {s !== "all" && <span className="ml-1.5 opacity-60">({countOf(s)})</span>}
          </button>
        ))}
      </div>

      {/* Error */}
      {error && (
        <div className={`p-3 rounded-xl border-l-4 border-red-500 text-sm ${isDarkMode ? "bg-red-500/10 text-red-300" : "bg-red-50 text-red-700"}`}>
          {error}
        </div>
      )}

      {/* Task List */}
      <div className="flex-1 overflow-y-auto space-y-3 custom-scrollbar pr-1">
        {loading && visibleTasks.length === 0 && (
          <div className="h-40 flex items-center justify-center opacity-30">
            <Loader2 size={32} className="animate-spin" />
          </div>
        )}
        {!loading && visibleTasks.length === 0 && (
          <div className={`h-48 flex flex-col items-center justify-center gap-3 opacity-30 border-2 border-dashed rounded-3xl ${isDarkMode ? "border-white/10" : "border-slate-200"}`}>
            <ClipboardList size={48} />
            <p>태스크가 없습니다.</p>
          </div>
        )}

        {visibleTasks.map((task) => {
          const cfg        = STATUS_CONFIG[task.status] || STATUS_CONFIG.unassigned;
          const isExpanded = expandedIds.has(task.id);
          const isMyTask   = task.assignee && task.assignee === currentUser?.name;
          const isDevGapApproval = task.task_type === "dev_gap_approval";
          const payload = task.payload || {};
          const pmReport = payload.pm_report || {};
          const prContext = payload.pr_context || {};
          const gapReport = Array.isArray(payload.gap_report) ? payload.gap_report : [];
          // author:xxrin
          // LLM fallback 상태를 PM이 놓치지 않도록 PM Report warning을 Dev GAP 카드에 표시한다.
          const llmWarnings = Array.isArray(pmReport.llm_warnings) ? pmReport.llm_warnings : [];
          const highGapCount = gapReport.filter((gap) => gap?.severity === "HIGH").length;

          return (
            <div key={task.id} className={`rounded-2xl border transition-all ${cfg.bg} ${cfg.border}`}>
              <button
                type="button"
                onClick={() => toggleExpand(task.id)}
                className="w-full flex items-center gap-3 p-4 text-left"
              >
                <cfg.Icon size={18} className={cfg.color} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={`text-xs font-bold px-2 py-0.5 rounded ${cfg.bg} ${cfg.color}`}>
                      {TASK_TYPE_LABEL[task.task_type] || task.task_type}
                    </span>
                    {task.area && (
                      <span className={`text-xs px-2 py-0.5 rounded font-semibold ${isDarkMode ? "bg-white/5 text-slate-400" : "bg-slate-100 text-slate-500"}`}>
                        {AREA_LABEL[task.area] || task.area}
                      </span>
                    )}
                    {task.effort && (
                      <span className="text-xs opacity-50 font-mono">{EFFORT_LABEL[task.effort] || task.effort}</span>
                    )}
                    <span className={`font-semibold text-sm truncate ${isDarkMode ? "text-slate-200" : "text-slate-800"}`}>
                      {task.title}
                    </span>
                  </div>
                  <p className="text-xs opacity-50 mt-0.5 flex items-center gap-1.5 flex-wrap">
                    <span>{task.created_at?.slice(0, 16).replace("T", " ")}</span>
                    {task.assignee
                      ? <span className="before:content-['·'] before:mr-1.5">{task.assignee}</span>
                      : <span className="before:content-['·'] before:mr-1.5 italic">미할당</span>
                    }
                    {task.feature_ref && <span className="before:content-['·'] before:mr-1.5 font-mono">{task.feature_ref}</span>}
                  </p>
                </div>
                <span className={`text-xs font-bold shrink-0 ${cfg.color}`}>{cfg.label}</span>
                {isExpanded ? <ChevronDown size={16} className="opacity-50 shrink-0" /> : <ChevronRight size={16} className="opacity-50 shrink-0" />}
              </button>

              {isExpanded && (
                <div className={`px-4 pb-4 space-y-3 border-t ${isDarkMode ? "border-white/5" : "border-slate-100"}`}>
                  {task.description && (
                    <p className="text-sm opacity-70 pt-3 leading-relaxed">{task.description}</p>
                  )}

                  {/* PM 액션: pending_approval → 승인(in_progress) / 거절(rejected) */}
                  {isDevGapApproval && (
                    <div className={`rounded-xl border p-3 space-y-2 ${isDarkMode ? "bg-black/20 border-white/10" : "bg-white border-slate-200"}`}>
                      <div className="flex flex-wrap items-center gap-2 text-xs font-semibold">
                        <span className={`px-2 py-1 rounded ${isDarkMode ? "bg-white/10 text-slate-200" : "bg-slate-100 text-slate-700"}`}>
                          PR #{prContext.pr_number || "-"}
                        </span>
                        <span className={`px-2 py-1 rounded font-mono ${isDarkMode ? "bg-white/10 text-slate-300" : "bg-slate-100 text-slate-600"}`}>
                          {prContext.branch_name || "unknown branch"}
                        </span>
                        <span className="px-2 py-1 rounded bg-red-500/10 text-red-400">
                          GAP {gapReport.length}
                        </span>
                        {highGapCount > 0 && (
                          <span className="px-2 py-1 rounded bg-orange-500/10 text-orange-400">
                            HIGH {highGapCount}
                          </span>
                        )}
                      </div>
                      {pmReport.summary && (
                        <p className="text-xs leading-relaxed opacity-80">{pmReport.summary}</p>
                      )}
                      {llmWarnings.length > 0 && (
                        <div className={`rounded-xl border p-3 space-y-2 ${isDarkMode ? "bg-yellow-500/10 border-yellow-500/20 text-yellow-100" : "bg-yellow-50 border-yellow-200 text-yellow-900"}`}>
                          <div className="flex items-center gap-2 text-xs font-bold">
                            <AlertTriangle size={14} className="shrink-0" />
                            <span>LLM analysis failed. Manual PM review required.</span>
                          </div>
                          <div className="space-y-1">
                            {llmWarnings.map((warning, index) => (
                              <p key={`${warning.node || "llm"}-${index}`} className="text-[11px] leading-relaxed opacity-85">
                                <span className="font-semibold">{warning.node || "llm"}:</span>{" "}
                                {warning.message || warning.llm_error_message || "Fallback analysis was used."}
                              </p>
                            ))}
                          </div>
                        </div>
                      )}
                      {Array.isArray(pmReport.recommended_pm_actions) && pmReport.recommended_pm_actions.length > 0 && (
                        <div className="flex flex-wrap gap-1.5">
                          {pmReport.recommended_pm_actions.map((action) => (
                            <span key={action} className={`text-[11px] px-2 py-0.5 rounded border ${isDarkMode ? "border-white/10 text-slate-300" : "border-slate-200 text-slate-600"}`}>
                              {action}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {isPM && task.status === "pending_approval" && (
                    <div className="flex gap-2 pt-1">
                      <button
                        onClick={() => handleAction(task.id, "in_progress")}
                        className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-500/10 transition-all"
                      >
                        <Check size={12} /> 승인
                      </button>
                      <button
                        onClick={() => handleAction(task.id, "rejected")}
                        className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/30 transition-all"
                      >
                        <X size={12} /> 거절
                      </button>
                    </div>
                  )}

                  {/* 작업자 액션: in_progress → PR대기중 */}
                  {isMyTask && task.status === "in_progress" && (
                    <div className="flex gap-2 pt-1">
                      <button
                        onClick={() => handleAction(task.id, "pr_pending")}
                        className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold bg-violet-600 hover:bg-violet-500 text-white shadow-lg shadow-violet-500/10 transition-all"
                      >
                        <GitPullRequest size={12} /> PR 제출
                      </button>
                    </div>
                  )}

                  {/* 삭제: completed / rejected 만 */}
                  {(task.status === "completed" || task.status === "rejected") && (
                    <div className="flex justify-end pt-1">
                      <button
                        onClick={() => handleDelete(task.id)}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold text-slate-500 hover:text-red-400 hover:bg-red-500/10 border border-transparent hover:border-red-500/20 transition-all"
                      >
                        <Trash2 size={12} /> 삭제
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
