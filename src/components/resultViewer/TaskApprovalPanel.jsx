import React, { useState, useEffect, useCallback } from "react";
import useAppStore from "../../store/useAppStore";
import {
  ClipboardList, Check, X, Clock, Loader2, RefreshCw,
  ChevronDown, ChevronRight, Zap, AlertTriangle, CheckCircle,
  XCircle, Github, Plus,
} from "lucide-react";

const STATUS_CONFIG = {
  pending:   { label: "대기중",   color: "text-yellow-400", bg: "bg-yellow-500/10",  border: "border-yellow-500/30",  Icon: Clock },
  approved:  { label: "승인됨",   color: "text-blue-400",   bg: "bg-blue-500/10",    border: "border-blue-500/30",    Icon: Check },
  rejected:  { label: "거절됨",   color: "text-red-400",    bg: "bg-red-500/10",     border: "border-red-500/30",     Icon: XCircle },
  completed: { label: "완료됨",   color: "text-emerald-400",bg: "bg-emerald-500/10", border: "border-emerald-500/30", Icon: CheckCircle },
  failed:    { label: "실패",     color: "text-orange-400", bg: "bg-orange-500/10",  border: "border-orange-500/30",  Icon: AlertTriangle },
};

const TASK_TYPE_LABEL = {
  publish_docs:  "설계 문서 퍼블리시",
  verify_sa:     "SA 검증",
  import_issues: "GitHub Issues 임포트",
  doc_sync:      "문서 동기화",
};

export default function TaskApprovalPanel() {
  const isDarkMode   = useAppStore((s) => s.isDarkMode);
  const userRole     = useAppStore((s) => s.userRole);
  const currentUser  = useAppStore((s) => s.currentUser);
  const backendPort  = useAppStore((s) => s.backendPort);
  const githubToken  = useAppStore((s) => s.githubToken);
  const githubOwner  = useAppStore((s) => s.githubOwner);
  const githubRepo   = useAppStore((s) => s.githubRepo);
  const resultData   = useAppStore((s) => s.resultData);

  const [tasks, setTasks]         = useState([]);
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState("");
  const [expandedIds, setExpandedIds] = useState(() => new Set());
  const [filterStatus, setFilterStatus] = useState("all");
  const [importLoading, setImportLoading] = useState(false);
  const [importMsg, setImportMsg] = useState("");

  const port    = backendPort || 8000;
  const isPM    = !userRole || userRole === "pm";
  const userId  = currentUser?.id || "";

  const fetchTasks = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const url = filterStatus === "all"
        ? `http://127.0.0.1:${port}/api/tasks`
        : `http://127.0.0.1:${port}/api/tasks?status=${filterStatus}`;
      const res = await fetch(url);
      const json = await res.json();
      if (json.status === "ok") setTasks(json.data);
      else setError(json.error || "조회 실패");
    } catch (e) { setError("서버 연결 실패: " + e.message); }
    finally { setLoading(false); }
  }, [port, filterStatus]);

  useEffect(() => { fetchTasks(); }, [fetchTasks]);

  const handleAction = async (taskId, action) => {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/api/tasks/${taskId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: action, reviewed_by: userId }),
      });
      const json = await res.json();
      if (json.status === "ok") {
        setTasks((prev) => prev.map((t) => t.id === taskId ? json.data : t));
      } else {
        setError(json.error || "업데이트 실패");
      }
    } catch (e) { setError("서버 연결 실패: " + e.message); }
  };

  const handleCreatePublishTask = async () => {
    if (!resultData) { setError("분석 결과가 없습니다."); return; }
    try {
      const res = await fetch(`http://127.0.0.1:${port}/api/tasks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          task_type: "publish_docs",
          title: "SA 설계 문서 GitHub 퍼블리시",
          description: "현재 SA 분석 결과를 GitHub Issues에 퍼블리시합니다.",
          payload: {
            result_data: resultData,
            token: githubToken,
            owner: githubOwner,
            repo: githubRepo,
            page_title: "SA 설계 문서",
          },
          created_by: userId,
        }),
      });
      const json = await res.json();
      if (json.status === "ok") { fetchTasks(); }
      else setError(json.error || "태스크 생성 실패");
    } catch (e) { setError("서버 연결 실패: " + e.message); }
  };

  const handleImportIssues = async () => {
    if (!githubToken || !githubOwner || !githubRepo) {
      setImportMsg("GitHub 설정이 필요합니다. 설정 패널에서 입력하세요.");
      return;
    }
    setImportLoading(true); setImportMsg("");
    try {
      const res = await fetch(`http://127.0.0.1:${port}/api/github/issues/import`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: githubToken, owner: githubOwner, repo: githubRepo }),
      });
      const json = await res.json();
      if (json.status === "ok") {
        setImportMsg(`${json.issue_count}개 이슈 임포트 태스크 생성됨 (PM 승인 대기)`);
        fetchTasks();
      } else {
        setImportMsg("실패: " + (json.error || "unknown"));
      }
    } catch (e) { setImportMsg("연결 실패: " + e.message); }
    finally { setImportLoading(false); }
  };

  const toggleExpand = (id) =>
    setExpandedIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const visibleTasks = filterStatus === "all"
    ? tasks
    : tasks.filter((t) => t.status === filterStatus);

  return (
    <div className={`h-full flex flex-col p-6 space-y-5 ${isDarkMode ? "text-slate-300" : "text-slate-800"}`}>
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className={`text-2xl font-black tracking-tight flex items-center gap-2 ${isDarkMode ? "text-white" : "text-slate-900"}`}>
            <ClipboardList size={22} /> 태스크 승인 관리
          </h2>
          <p className="text-sm opacity-60 mt-1">
            {isPM ? "PM으로서 대기 중인 태스크를 승인하거나 거절할 수 있습니다." : "태스크 목록을 확인합니다."}
          </p>
        </div>
        <button
          onClick={fetchTasks}
          disabled={loading}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-bold transition-all ${
            isDarkMode ? "bg-white/5 hover:bg-white/10" : "bg-slate-100 hover:bg-slate-200 border border-slate-200"
          }`}
        >
          {loading ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
          새로고침
        </button>
      </div>

      {/* Quick Actions (PM only) */}
      {isPM && (
        <div className={`p-4 rounded-2xl border space-y-3 ${isDarkMode ? "bg-white/5 border-white/10" : "bg-white border-slate-200 shadow-sm"}`}>
          <p className="text-xs font-bold uppercase tracking-wider opacity-60">빠른 태스크 생성</p>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={handleCreatePublishTask}
              disabled={!resultData}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all ${
                resultData
                  ? "bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-500/10"
                  : "bg-white/5 text-slate-500 cursor-not-allowed"
              }`}
            >
              <Plus size={12} /> 설계 문서 퍼블리시 태스크
            </button>
            <button
              onClick={handleImportIssues}
              disabled={importLoading || !githubToken}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all ${
                githubToken && !importLoading
                  ? "bg-slate-700 hover:bg-slate-600 text-white"
                  : "bg-white/5 text-slate-500 cursor-not-allowed"
              }`}
            >
              {importLoading ? <Loader2 size={12} className="animate-spin" /> : <Github size={12} />}
              GitHub Issues 임포트
            </button>
          </div>
          {importMsg && (
            <p className={`text-xs ${importMsg.startsWith("실패") || importMsg.startsWith("연결") ? "text-red-400" : "text-emerald-400"}`}>
              {importMsg}
            </p>
          )}
        </div>
      )}

      {/* Filter */}
      <div className="flex gap-2 flex-wrap">
        {["all", "pending", "approved", "completed", "rejected"].map((s) => (
          <button
            key={s}
            onClick={() => setFilterStatus(s)}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
              filterStatus === s
                ? isDarkMode
                  ? "bg-white/15 text-white"
                  : "bg-slate-800 text-white"
                : isDarkMode
                ? "bg-white/5 text-slate-400 hover:text-slate-200"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            {s === "all" ? "전체" : STATUS_CONFIG[s]?.label || s}
            {s !== "all" && (
              <span className="ml-1.5 opacity-60">
                ({tasks.filter((t) => t.status === s).length})
              </span>
            )}
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
          const cfg = STATUS_CONFIG[task.status] || STATUS_CONFIG.pending;
          const isExpanded = expandedIds.has(task.id);
          return (
            <div
              key={task.id}
              className={`rounded-2xl border transition-all ${cfg.bg} ${cfg.border} ${isDarkMode ? "" : "shadow-sm"}`}
            >
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
                    <span className={`font-semibold text-sm ${isDarkMode ? "text-slate-200" : "text-slate-800"}`}>
                      {task.title}
                    </span>
                  </div>
                  <p className="text-xs opacity-50 mt-0.5">
                    {task.created_at?.slice(0, 16).replace("T", " ")}
                    {task.reviewed_by && ` · 검토: ${task.reviewed_by}`}
                  </p>
                </div>
                <span className={`text-xs font-bold ${cfg.color}`}>{cfg.label}</span>
                {isExpanded ? <ChevronDown size={16} className="opacity-50 shrink-0" /> : <ChevronRight size={16} className="opacity-50 shrink-0" />}
              </button>

              {isExpanded && (
                <div className={`px-4 pb-4 space-y-3 border-t ${isDarkMode ? "border-white/5" : "border-slate-100"} animate-fade-in`}>
                  {task.description && (
                    <p className="text-sm opacity-70 pt-3">{task.description}</p>
                  )}
                  {task.result && (
                    <div className={`p-3 rounded-xl text-xs font-mono whitespace-pre-wrap ${isDarkMode ? "bg-black/20 text-slate-400" : "bg-slate-50 text-slate-600 border border-slate-200"}`}>
                      {task.result}
                    </div>
                  )}

                  {/* PM Actions */}
                  {isPM && task.status === "pending" && (
                    <div className="flex gap-2 pt-1">
                      <button
                        onClick={() => handleAction(task.id, "approved")}
                        className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-500/10 transition-all"
                      >
                        <Check size={12} /> 승인 및 실행
                      </button>
                      <button
                        onClick={() => handleAction(task.id, "rejected")}
                        className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/30 transition-all"
                      >
                        <X size={12} /> 거절
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
