import React, { useState, useEffect, useMemo } from "react";
import useAppStore from "../../store/useAppStore";
import { synthesizeMemoIdea } from "../../store/storeHelpers";
import {
  StickyNote, Trash2, Search, Filter, RefreshCw, Zap,
  CheckSquare, Square, Archive, ListChecks, X, Eye,
  ChevronDown, ChevronRight, FileText,
} from "lucide-react";

const SECTION_MAP = {
  overview: "분석 개요",
  rtm: "요구사항(RTM)",
  stack: "기술 스택",
  sa_overview: "아키텍처 분석",
  sa_components: "컴포넌트 설계",
  sa_api: "API 설계",
  sa_db: "데이터베이스 설계",
  memo: "메모 관리",
  "Idea Chat": "AI 채팅",
  "Chat Request": "AI 채팅",
};

export default function MemoManager() {
  const isDarkMode = useAppStore((s) => s.isDarkMode);
  const userComments = useAppStore((s) => s.userComments);
  const removeComment = useAppStore((s) => s.removeComment);
  const syncMemos = useAppStore((s) => s.syncMemos);
  const startMemoDrivenUpdate = useAppStore((s) => s.startMemoDrivenUpdate);
  const pipelineStatus = useAppStore((s) => s.pipelineStatus);
  const userRole = useAppStore((s) => s.userRole);
  const canEdit = !userRole || userRole === "pm" || userRole === "engineer";

  const [searchTerm, setSearchTerm] = useState("");
  const [filterSection, setFilterSection] = useState("All");
  const [viewMode, setViewMode] = useState("active"); // "active" | "applied"
  const [selectedIds, setSelectedIds] = useState(() => new Set());
  const [expandedIds, setExpandedIds] = useState(() => new Set()); // detail 펼침 토글
  const [showConfirmModal, setShowConfirmModal] = useState(false);

  const toggleExpand = (id) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  useEffect(() => { syncMemos(); }, []);

  // 뷰 모드 전환 시 선택 상태 초기화 (active의 선택이 applied 모드로 새지 않도록)
  useEffect(() => { setSelectedIds(new Set()); }, [viewMode]);

  const isRunning = pipelineStatus === "running";

  // viewMode 별 필터 → 섹션/검색 필터
  const visibleByMode = useMemo(
    () => userComments.filter((m) => (viewMode === "applied" ? !!m.applied : !m.applied)),
    [userComments, viewMode]
  );

  const sections = useMemo(
    () => ["All", ...new Set(visibleByMode.map((c) => c.section).filter(Boolean))],
    [visibleByMode]
  );

  const filteredMemos = useMemo(() => {
    return visibleByMode.filter((memo) => {
      const term = searchTerm.toLowerCase();
      const matchesSearch =
        !term ||
        memo.text.toLowerCase().includes(term) ||
        memo.selectedText?.toLowerCase().includes(term);
      const matchesFilter = filterSection === "All" || memo.section === filterSection;
      return matchesSearch && matchesFilter;
    });
  }, [visibleByMode, searchTerm, filterSection]);

  const selectedMemos = useMemo(
    () => userComments.filter((c) => selectedIds.has(c.id)),
    [userComments, selectedIds]
  );

  const toggleSelect = (id) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectAll = () => setSelectedIds(new Set(filteredMemos.map((m) => m.id)));
  const clearSelection = () => setSelectedIds(new Set());

  const canTriggerUpdate =
    viewMode === "active" && selectedIds.size > 0 && !isRunning && canEdit;

  const handleConfirm = () => {
    setShowConfirmModal(false);
    startMemoDrivenUpdate(Array.from(selectedIds));
    setSelectedIds(new Set());
  };

  const previewIdea = useMemo(
    () => (selectedMemos.length > 0 ? synthesizeMemoIdea(selectedMemos) : ""),
    [selectedMemos]
  );

  return (
    <div className={`h-full flex flex-col p-6 space-y-6 ${isDarkMode ? "text-slate-300" : "text-slate-800"}`}>
      <div className="flex flex-col gap-4">
        <h2 className={`text-2xl font-black tracking-tight ${isDarkMode ? "text-white" : "text-slate-900"}`}>
          전체 메모 관리
        </h2>
        <p className="text-sm opacity-60">
          프로젝트 수행 중 기록된 모든 지적사항과 메모를 중앙에서 관리합니다.
        </p>
      </div>

      {/* ── 뷰 모드 토글 ─────────────────────── */}
      <div className="flex items-center gap-2">
        <ViewModeButton
          active={viewMode === "active"}
          onClick={() => setViewMode("active")}
          isDarkMode={isDarkMode}
          Icon={ListChecks}
          label={`활성 메모 (${userComments.filter((m) => !m.applied).length})`}
        />
        <ViewModeButton
          active={viewMode === "applied"}
          onClick={() => setViewMode("applied")}
          isDarkMode={isDarkMode}
          Icon={Archive}
          label={`이전 메모 (${userComments.filter((m) => !!m.applied).length})`}
        />
      </div>

      {/* ── 검색 / 섹션 필터 / 일괄 선택 ──────── */}
      <div className="flex flex-wrap items-center gap-3">
        <div className={`flex-1 min-w-[200px] flex items-center gap-2 px-3 py-2 rounded-xl border ${isDarkMode ? "bg-white/5 border-white/10" : "bg-slate-50 border-slate-200"}`}>
          <Search size={16} className="text-slate-500" />
          <input
            type="text"
            placeholder="메모 검색..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="bg-transparent border-none outline-none text-sm w-full"
          />
        </div>
        <div className={`flex items-center gap-2 px-3 py-2 rounded-xl border ${isDarkMode ? "bg-white/5 border-white/10" : "bg-slate-50 border-slate-200"}`}>
          <Filter size={16} className="text-slate-500" />
          <select
            value={filterSection}
            onChange={(e) => setFilterSection(e.target.value)}
            className="bg-transparent border-none outline-none text-sm cursor-pointer"
          >
            {sections.map((s) => (
              <option key={s} value={s}>{SECTION_MAP[s] || s}</option>
            ))}
          </select>
        </div>

        {viewMode === "active" && filteredMemos.length > 0 && (
          <div className="flex items-center gap-2 ml-auto">
            <button
              onClick={selectAll}
              className={`px-3 py-2 rounded-xl text-xs font-medium transition-colors ${isDarkMode ? "bg-white/5 hover:bg-white/10" : "bg-slate-50 hover:bg-slate-100 border border-slate-200"}`}
            >
              전체 선택
            </button>
            <button
              onClick={clearSelection}
              disabled={selectedIds.size === 0}
              className={`px-3 py-2 rounded-xl text-xs font-medium transition-colors disabled:opacity-40 ${isDarkMode ? "bg-white/5 hover:bg-white/10" : "bg-slate-50 hover:bg-slate-100 border border-slate-200"}`}
            >
              선택 해제
            </button>
          </div>
        )}
      </div>

      {/* ── 메모 리스트 ──────────────────── */}
      <div className="flex-1 overflow-y-auto space-y-3 pr-2 custom-scrollbar">
        {filteredMemos.length === 0 ? (
          <div className="h-64 flex flex-col items-center justify-center opacity-20 border-2 border-dashed border-white/10 rounded-3xl">
            <StickyNote size={48} className="mb-4" />
            <p>
              {viewMode === "applied"
                ? "이전에 반영된 메모가 없습니다."
                : "검색 결과가 없거나 작성된 메모가 없습니다."}
            </p>
          </div>
        ) : (
          filteredMemos.map((memo) => {
            const isSelected = selectedIds.has(memo.id);
            const isApplied = !!memo.applied;
            const hasDetail = !!(memo.detail && memo.detail.trim());
            const isExpanded = expandedIds.has(memo.id);
            return (
              <div
                key={memo.id}
                className={`group p-5 rounded-2xl border transition-all ${
                  isApplied
                    ? `opacity-60 ${isDarkMode ? "bg-white/[0.02] border-white/5" : "bg-slate-50 border-slate-200"}`
                    : isSelected
                    ? `scale-[1.005] ${isDarkMode ? "bg-blue-500/5 border-blue-500/40 shadow-[0_0_20px_rgba(59,130,246,0.08)]" : "bg-blue-50/50 border-blue-300 shadow-sm"}`
                    : `hover:scale-[1.005] ${isDarkMode ? "bg-white/5 border-white/5 hover:border-white/20" : "bg-white border-slate-200 shadow-sm hover:shadow-md"}`
                }`}
              >
                <div className="flex items-start gap-4">
                  {/* 체크박스 (active 모드에서만 활성) */}
                  {viewMode === "active" ? (
                    <button
                      onClick={() => toggleSelect(memo.id)}
                      className={`mt-1 shrink-0 transition-colors ${isSelected ? "text-blue-500" : "text-slate-500 hover:text-slate-300"}`}
                      title={isSelected ? "선택 해제" : "선택"}
                    >
                      {isSelected ? <CheckSquare size={20} /> : <Square size={20} />}
                    </button>
                  ) : (
                    <div className="mt-1 shrink-0">
                      <Archive size={18} className="text-slate-500" />
                    </div>
                  )}

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-2 flex-wrap">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${isDarkMode ? "bg-blue-500/20 text-blue-300" : "bg-blue-50 text-blue-600"}`}>
                        {SECTION_MAP[memo.section] || memo.section}
                      </span>
                      {isApplied && (
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${isDarkMode ? "bg-emerald-500/20 text-emerald-300" : "bg-emerald-50 text-emerald-700"}`}
                          title={memo.appliedAt || ""}
                        >
                          반영됨
                        </span>
                      )}
                      {hasDetail && (
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider flex items-center gap-1 ${isDarkMode ? "bg-purple-500/15 text-purple-300" : "bg-purple-50 text-purple-700"}`}
                          title="상세 내용 있음"
                        >
                          <FileText size={10} /> 상세
                        </span>
                      )}
                    </div>

                    {/* 제목 + 토글 */}
                    <button
                      type="button"
                      onClick={() => hasDetail && toggleExpand(memo.id)}
                      disabled={!hasDetail}
                      className={`text-left w-full flex items-start gap-2 mb-2 ${hasDetail ? "cursor-pointer" : "cursor-default"}`}
                    >
                      {hasDetail && (
                        <span className={`mt-1 shrink-0 transition-transform ${isExpanded ? "rotate-0" : "-rotate-90"} ${isDarkMode ? "text-slate-400" : "text-slate-500"}`}>
                          <ChevronDown size={16} />
                        </span>
                      )}
                      <h3 className={`text-base font-bold flex-1 min-w-0 ${isDarkMode ? "text-slate-100" : "text-slate-800"}`}>
                        {memo.text}
                      </h3>
                    </button>

                    {memo.selectedText && (
                      <div className={`p-3 rounded-xl text-sm italic mb-1 border-l-4 ${isDarkMode ? "bg-black/20 border-blue-500/40 text-slate-400" : "bg-slate-50 border-blue-200 text-slate-500"}`}>
                        "{memo.selectedText}"
                      </div>
                    )}

                    {/* 상세 내용 (토글 펼침 시) */}
                    {hasDetail && isExpanded && (
                      <div
                        className={`mt-2 p-4 rounded-xl text-sm leading-relaxed whitespace-pre-wrap border-l-4 animate-fade-in ${isDarkMode ? "bg-purple-500/[0.06] border-purple-400/40 text-slate-300" : "bg-purple-50/50 border-purple-300 text-slate-700"}`}
                      >
                        <div className={`text-[10px] font-bold uppercase tracking-wider mb-2 ${isDarkMode ? "text-purple-300" : "text-purple-700"}`}>
                          상세 수정 사항
                        </div>
                        {memo.detail}
                      </div>
                    )}
                  </div>

                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={() => removeComment(memo.id)}
                      className="p-2 rounded-lg hover:bg-red-500/10 text-slate-500 hover:text-red-500 transition-colors"
                      title="삭제"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* ── 하단 액션 (active 모드에서만) ───── */}
      {viewMode === "active" && userComments.filter((m) => !m.applied).length > 0 && (
        <div className="pt-4 border-t border-white/10">
          {!canEdit && (
            <p className={`text-center text-xs mb-3 py-2 px-4 rounded-xl ${isDarkMode ? "bg-amber-500/10 text-amber-300" : "bg-amber-50 text-amber-700 border border-amber-200"}`}>
              viewer 역할은 메모 반영 업데이트를 실행할 수 없습니다.
            </p>
          )}
          <button
            onClick={() => setShowConfirmModal(true)}
            disabled={!canTriggerUpdate}
            className={`w-full flex items-center justify-center gap-3 py-4 rounded-2xl font-bold text-lg shadow-lg transition-all group ${
              canTriggerUpdate
                ? "bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white shadow-blue-500/20 hover:scale-[1.01] active:scale-[0.99]"
                : "bg-white/5 text-slate-500 cursor-not-allowed"
            }`}
          >
            <RefreshCw size={20} className={canTriggerUpdate ? "group-hover:rotate-180 transition-transform duration-700" : ""} />
            <span>
              {isRunning
                ? "분석 진행 중..."
                : selectedIds.size > 0
                ? `선택한 ${selectedIds.size}건 반영 업데이트`
                : "지적사항 반영 설계 업데이트 (메모를 선택하세요)"}
            </span>
            {canTriggerUpdate && <Zap size={18} className="text-yellow-400 fill-yellow-400 animate-pulse" />}
          </button>
          <p className="text-center text-[11px] mt-3 opacity-40">
            선택한 메모를 idea 텍스트로 합성해 UPDATE 모드 분석을 실행합니다. 성공 시 메모는 "이전 메모"로 이동합니다.
          </p>
        </div>
      )}

      {/* ── 확인 모달 ───────────────────── */}
      {showConfirmModal && (
        <ConfirmModal
          isDarkMode={isDarkMode}
          memos={selectedMemos}
          previewIdea={previewIdea}
          onCancel={() => setShowConfirmModal(false)}
          onConfirm={handleConfirm}
        />
      )}
    </div>
  );
}

// ── 보조 컴포넌트 ───────────────────────────

function ViewModeButton({ active, onClick, Icon, label, isDarkMode }) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 rounded-xl text-sm font-bold flex items-center gap-2 transition-all ${
        active
          ? isDarkMode
            ? "bg-[var(--accent)]/20 text-[var(--accent)] border border-[var(--accent)]/40"
            : "bg-blue-100 text-blue-700 border border-blue-200"
          : isDarkMode
          ? "bg-white/5 text-slate-400 hover:text-slate-200 border border-white/5 hover:border-white/10"
          : "bg-slate-50 text-slate-600 hover:text-slate-900 border border-slate-200 hover:bg-slate-100"
      }`}
    >
      <Icon size={16} />
      {label}
    </button>
  );
}

function ConfirmModal({ isDarkMode, memos, previewIdea, onCancel, onConfirm }) {
  const [showRawIdea, setShowRawIdea] = useState(false);

  return (
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center bg-black/60 backdrop-blur-sm p-8"
      onClick={onCancel}
    >
      <div
        className={`w-[640px] max-h-[85vh] rounded-2xl shadow-2xl flex flex-col overflow-hidden ${isDarkMode ? "bg-[#1e1e24] border border-white/10" : "bg-white border border-slate-200"}`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className={`flex items-center justify-between px-6 py-4 border-b ${isDarkMode ? "border-white/5" : "border-slate-200"}`}>
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-blue-500/15 flex items-center justify-center">
              <RefreshCw size={18} className="text-blue-500" />
            </div>
            <div>
              <h2 className={`text-[15px] font-bold ${isDarkMode ? "text-slate-100" : "text-slate-900"}`}>
                메모 반영 UPDATE 시작
              </h2>
              <p className="text-[11px] opacity-60">
                선택한 {memos.length}건의 메모가 UPDATE 분석에 전달됩니다
              </p>
            </div>
          </div>
          <button
            onClick={onCancel}
            className={`p-1.5 rounded-full transition-colors ${isDarkMode ? "hover:bg-white/10 text-slate-400" : "hover:bg-slate-100 text-slate-500"}`}
            title="닫기"
          >
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 overflow-y-auto flex-1 custom-scrollbar">
          <div className="mb-4">
            <h3 className={`text-xs font-bold uppercase tracking-wider mb-3 ${isDarkMode ? "text-slate-400" : "text-slate-500"}`}>
              선택된 메모 ({memos.length})
            </h3>
            <ul className="space-y-2">
              {memos.map((m) => {
                const hasDetail = !!(m.detail && m.detail.trim());
                return (
                  <li
                    key={m.id}
                    className={`p-3 rounded-xl border-l-4 border-blue-500 ${isDarkMode ? "bg-white/5" : "bg-slate-50"}`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider ${isDarkMode ? "bg-blue-500/20 text-blue-300" : "bg-blue-50 text-blue-700"}`}>
                        {SECTION_MAP[m.section] || m.section}
                      </span>
                      {hasDetail && (
                        <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider flex items-center gap-1 ${isDarkMode ? "bg-purple-500/15 text-purple-300" : "bg-purple-50 text-purple-700"}`}>
                          <FileText size={9} /> 상세
                        </span>
                      )}
                    </div>
                    <p className={`text-sm font-medium ${isDarkMode ? "text-slate-200" : "text-slate-800"}`}>
                      {m.text}
                    </p>
                    {m.selectedText && (
                      <p className={`text-xs italic mt-1 opacity-60 line-clamp-2`}>
                        "{m.selectedText}"
                      </p>
                    )}
                    {hasDetail && (
                      <div className={`mt-2 p-2 rounded-lg text-xs whitespace-pre-wrap leading-relaxed ${isDarkMode ? "bg-black/20 text-slate-400" : "bg-white text-slate-600 border border-slate-200"}`}>
                        {m.detail}
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>

          <div className="mt-4">
            <button
              onClick={() => setShowRawIdea((v) => !v)}
              className={`flex items-center gap-2 text-xs font-medium transition-colors ${isDarkMode ? "text-slate-400 hover:text-slate-200" : "text-slate-500 hover:text-slate-800"}`}
            >
              <Eye size={14} />
              {showRawIdea ? "LLM 전달 idea 텍스트 숨기기" : "LLM 전달 idea 텍스트 미리보기"}
            </button>
            {showRawIdea && (
              <pre className={`mt-2 p-3 rounded-xl text-[11px] leading-relaxed whitespace-pre-wrap break-words max-h-60 overflow-y-auto custom-scrollbar ${isDarkMode ? "bg-black/30 text-slate-300" : "bg-slate-50 text-slate-700 border border-slate-200"}`}>
                {previewIdea}
              </pre>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className={`flex justify-end gap-2 px-6 py-4 border-t ${isDarkMode ? "border-white/5" : "border-slate-200"}`}>
          <button
            onClick={onCancel}
            className={`px-5 py-2 rounded-lg text-sm font-bold transition-colors ${isDarkMode ? "bg-white/5 hover:bg-white/10 text-slate-200" : "bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200"}`}
          >
            취소
          </button>
          <button
            onClick={onConfirm}
            className="px-5 py-2 rounded-lg text-sm font-bold bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white shadow-lg shadow-blue-500/20 transition-all flex items-center gap-2"
          >
            <Zap size={14} className="text-yellow-300 fill-yellow-300" />
            UPDATE 실행
          </button>
        </div>
      </div>
    </div>
  );
}
