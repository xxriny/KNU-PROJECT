import React, { useEffect, useRef, useState } from "react";
import {
  Rocket, X, Sparkles, Layers, MessageSquare, StickyNote,
  Wand2, Loader2, AlertTriangle, ChevronDown, Trash2,
} from "lucide-react";
import useAppStore from "../store/useAppStore";

/**
 * 🚀 Sync 확인 모달 — Pre-flight 요약 + 사용자 검토/편집 → 빌드
 *
 * 흐름:
 * 1. 모달이 열리면 store.extractFinalIdea()를 호출, 날것 대화·메모를
 *    LLM 1회로 정제해 '최종 확정 요구사항' 마크다운을 받는다.
 * 2. 결과는 편집 가능한 textarea로 노출. 사용자가 그대로 쓰거나 다듬을 수 있다.
 * 3. [적용 및 빌드] 클릭 시 textarea 내용을 ideaOverride로 onConfirm에 전달.
 *    무거운 PM/SA 파이프라인은 이 깨끗한 입력만 보게 된다.
 */
export default function SyncConfirmModal({
  open,
  isDarkMode,
  isFirstBuild,
  targetVersion,
  chatDiff,
  activeMemos,
  onCancel,
  onConfirm,
}) {
  const extractFinalIdea = useAppStore((s) => s.extractFinalIdea);

  const [isExtracting, setIsExtracting] = useState(false);
  const [extractError, setExtractError] = useState("");
  const [editedText, setEditedText] = useState("");
  const [droppedPoints, setDroppedPoints] = useState([]);
  const [showOriginals, setShowOriginals] = useState(false);
  const textareaRef = useRef(null);

  const diffCount = (chatDiff || []).length;
  const memoCount = (activeMemos || []).length;
  const hasRawChanges = diffCount > 0 || memoCount > 0;
  const trimmedFinal = editedText.trim();
  const canConfirm = !isExtracting && !!trimmedFinal;

  const modeMeta = isFirstBuild
    ? {
        label: "신규 빌드 (CREATE)",
        sub: "Zero to One — 정제된 요구사항으로 v1.0 설계서를 처음 만듭니다.",
        Icon: Sparkles,
        accent: "from-blue-500 to-cyan-500",
        ring: "ring-blue-400/40",
      }
    : {
        label: "기능 확장 (UPDATE)",
        sub: "기존 설계서를 베이스로 정제된 변경 요청만 안전하게 병합합니다.",
        Icon: Layers,
        accent: "from-emerald-500 to-teal-500",
        ring: "ring-emerald-400/40",
      };

  const confirmLabel = isFirstBuild ? "🚀 적용 및 설계 시작" : "🚀 적용 및 업데이트";

  // 모달 열림 → Pre-flight 요약 자동 호출
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setIsExtracting(true);
    setExtractError("");
    setEditedText("");
    setDroppedPoints([]);
    setShowOriginals(false);

    if (!hasRawChanges) {
      setIsExtracting(false);
      return () => { cancelled = true; };
    }

    extractFinalIdea()
      .then((res) => {
        if (cancelled) return;
        if (res?.status === "ok") {
          setEditedText(res.summary_markdown || "");
          setDroppedPoints(res.dropped_points || []);
          setExtractError("");
        } else {
          setExtractError(res?.error || "요약 추출에 실패했습니다.");
        }
      })
      .catch((e) => {
        if (!cancelled) setExtractError(e?.message || String(e));
      })
      .finally(() => {
        if (!cancelled) setIsExtracting(false);
      });

    return () => { cancelled = true; };
    // hasRawChanges는 chatDiff/activeMemos 길이에 의해 결정되므로 의존성 폭주 방지를
    // 위해 open만 트리거로 사용. 동일 데이터 재호출은 의도된 동작.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // ESC 닫기 / Ctrl+Enter 수락
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => {
      if (e.key === "Escape") onCancel?.();
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey) && canConfirm) {
        onConfirm?.(trimmedFinal);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onCancel, onConfirm, canConfirm, trimmedFinal]);

  // textarea 높이 자동 조절
  useEffect(() => {
    if (!textareaRef.current) return;
    textareaRef.current.style.height = "auto";
    textareaRef.current.style.height =
      Math.min(textareaRef.current.scrollHeight, 320) + "px";
  }, [editedText, open]);

  if (!open) return null;

  const handleConfirm = () => {
    if (!canConfirm) return;
    onConfirm?.(trimmedFinal);
  };

  const handleRetry = () => {
    setIsExtracting(true);
    setExtractError("");
    extractFinalIdea()
      .then((res) => {
        if (res?.status === "ok") {
          setEditedText(res.summary_markdown || "");
          setDroppedPoints(res.dropped_points || []);
        } else {
          setExtractError(res?.error || "요약 추출에 실패했습니다.");
        }
      })
      .finally(() => setIsExtracting(false));
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center px-4 animate-fade-in"
      role="dialog"
      aria-modal="true"
      aria-labelledby="sync-confirm-title"
    >
      <div
        className="absolute inset-0 bg-slate-950/60 backdrop-blur-sm"
        onClick={onCancel}
      />

      <div
        className={`
          relative w-full max-w-2xl rounded-3xl border shadow-2xl overflow-hidden
          ${isDarkMode
            ? "bg-[#0F1219] border-white/10 text-slate-200"
            : "bg-white border-slate-200 text-slate-800"
          }
        `}
      >
        {/* Header */}
        <div
          className={`relative px-6 pt-6 pb-5 border-b ${
            isDarkMode ? "border-white/5" : "border-slate-100"
          }`}
        >
          <button
            onClick={onCancel}
            title="닫기 (Esc)"
            className={`absolute top-4 right-4 w-8 h-8 flex items-center justify-center rounded-full transition-colors ${
              isDarkMode
                ? "hover:bg-white/10 text-slate-400 hover:text-slate-200"
                : "hover:bg-slate-100 text-slate-500 hover:text-slate-700"
            }`}
          >
            <X size={16} />
          </button>

          <div className="flex items-start gap-3">
            <div
              className={`w-11 h-11 shrink-0 flex items-center justify-center rounded-2xl bg-gradient-to-br ${modeMeta.accent} text-white shadow-lg ring-2 ${modeMeta.ring}`}
            >
              <Rocket size={20} />
            </div>
            <div className="flex-1 min-w-0">
              <h2
                id="sync-confirm-title"
                className="text-[16px] font-black tracking-tight"
              >
                설계서 업데이트 확인
              </h2>
              <p
                className={`mt-1 text-[12px] font-medium leading-snug ${
                  isDarkMode ? "text-slate-400" : "text-slate-500"
                }`}
              >
                AI가 대화·메모에서 노이즈를 제거한 <b>최종 확정 요구사항</b>입니다.
                필요하면 직접 수정한 뒤 빌드하세요.
              </p>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <span
              className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-bold bg-gradient-to-r ${modeMeta.accent} text-white shadow-sm`}
            >
              <modeMeta.Icon size={12} />
              {modeMeta.label}
            </span>
            <span
              className={`inline-flex items-center px-3 py-1 rounded-full text-[11px] font-bold border ${
                isDarkMode
                  ? "bg-white/[0.04] border-white/10 text-slate-200"
                  : "bg-slate-50 border-slate-200 text-slate-700"
              }`}
            >
              타깃 버전 · {targetVersion}
            </span>
          </div>
          <p
            className={`mt-2 text-[11px] leading-relaxed ${
              isDarkMode ? "text-slate-500" : "text-slate-500"
            }`}
          >
            {modeMeta.sub}
          </p>
        </div>

        {/* Body */}
        <div className="px-6 py-5 max-h-[60vh] overflow-y-auto space-y-5">
          {!hasRawChanges && (
            <div
              className={`px-4 py-3 rounded-2xl border text-[12px] font-medium ${
                isDarkMode
                  ? "bg-amber-500/10 border-amber-500/20 text-amber-300"
                  : "bg-amber-50 border-amber-200 text-amber-700"
              }`}
            >
              반영할 새 대화나 활성 메모가 없습니다. 먼저 아이디어를 대화로
              정리하거나 메모를 추가해주세요.
            </div>
          )}

          {hasRawChanges && (
            <section>
              <div className="flex items-center justify-between gap-2 mb-2">
                <div className="flex items-center gap-2">
                  <Wand2
                    size={13}
                    className={isDarkMode ? "text-blue-300" : "text-blue-600"}
                  />
                  <h3
                    className={`text-[11px] font-black uppercase tracking-[0.18em] ${
                      isDarkMode ? "text-slate-300" : "text-slate-700"
                    }`}
                  >
                    AI 정제 결과
                  </h3>
                </div>
                {!isExtracting && !extractError && (
                  <button
                    onClick={handleRetry}
                    title="다시 추출"
                    className={`text-[11px] font-bold px-2 py-1 rounded-md transition-colors ${
                      isDarkMode
                        ? "text-slate-400 hover:text-slate-100 hover:bg-white/[0.06]"
                        : "text-slate-500 hover:text-slate-800 hover:bg-slate-100"
                    }`}
                  >
                    ↻ 다시 추출
                  </button>
                )}
              </div>

              {isExtracting && (
                <div
                  className={`px-4 py-6 rounded-2xl border flex items-center justify-center gap-3 ${
                    isDarkMode
                      ? "bg-white/[0.02] border-white/5 text-slate-400"
                      : "bg-slate-50/60 border-slate-200 text-slate-500"
                  }`}
                >
                  <Loader2 size={16} className="animate-spin text-blue-500" />
                  <span className="text-[12px] font-medium">
                    대화·메모에서 최종 합의된 요구사항을 정리 중...
                  </span>
                </div>
              )}

              {!isExtracting && extractError && (
                <div
                  className={`px-4 py-3 rounded-2xl border flex items-start gap-2 ${
                    isDarkMode
                      ? "bg-rose-500/10 border-rose-500/20 text-rose-300"
                      : "bg-rose-50 border-rose-200 text-rose-700"
                  }`}
                >
                  <AlertTriangle size={14} className="mt-0.5 shrink-0" />
                  <div className="flex-1 text-[12px] font-medium leading-snug">
                    <div>정제 단계 실패: {extractError}</div>
                    <button
                      onClick={handleRetry}
                      className={`mt-1 text-[11px] font-bold underline ${
                        isDarkMode ? "text-rose-200" : "text-rose-800"
                      }`}
                    >
                      다시 시도
                    </button>
                  </div>
                </div>
              )}

              {!isExtracting && !extractError && (
                <textarea
                  ref={textareaRef}
                  value={editedText}
                  onChange={(e) => setEditedText(e.target.value)}
                  placeholder="정제된 요구사항이 여기에 표시됩니다. 직접 수정해도 됩니다."
                  className={`
                    w-full rounded-2xl border px-4 py-3 text-[13px] leading-relaxed resize-none
                    font-mono whitespace-pre-wrap focus:outline-none focus:ring-2 transition-all
                    ${isDarkMode
                      ? "bg-white/[0.03] border-white/10 text-slate-100 placeholder:text-slate-600 focus:ring-blue-400/40 focus:border-blue-400/40"
                      : "bg-slate-50/60 border-slate-200 text-slate-800 placeholder:text-slate-400 focus:ring-blue-300 focus:border-blue-300"
                    }
                  `}
                  style={{ minHeight: "120px" }}
                />
              )}
            </section>
          )}

          {/* AI가 제외한 항목 */}
          {droppedPoints.length > 0 && (
            <section>
              <div className="flex items-center gap-2 mb-2">
                <Trash2
                  size={12}
                  className={isDarkMode ? "text-slate-500" : "text-slate-400"}
                />
                <h3
                  className={`text-[11px] font-black uppercase tracking-[0.18em] ${
                    isDarkMode ? "text-slate-400" : "text-slate-600"
                  }`}
                >
                  대화 중 취소된 항목
                </h3>
                <span
                  className={`px-1.5 py-0.5 rounded-full text-[10px] font-black ${
                    isDarkMode
                      ? "bg-white/[0.06] text-slate-300"
                      : "bg-slate-200 text-slate-700"
                  }`}
                >
                  {droppedPoints.length}
                </span>
              </div>
              <ul
                className={`space-y-1 rounded-2xl border p-3 ${
                  isDarkMode
                    ? "bg-white/[0.02] border-white/5"
                    : "bg-slate-50/60 border-slate-200"
                }`}
              >
                {droppedPoints.map((p, idx) => (
                  <li
                    key={idx}
                    className={`text-[12px] leading-snug line-through ${
                      isDarkMode ? "text-slate-500" : "text-slate-500"
                    }`}
                  >
                    {p}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* 원본 대화·메모 (collapsible) */}
          {hasRawChanges && (
            <section>
              <button
                onClick={() => setShowOriginals((v) => !v)}
                className={`flex items-center gap-2 text-[11px] font-bold uppercase tracking-[0.18em] transition-colors ${
                  isDarkMode
                    ? "text-slate-500 hover:text-slate-300"
                    : "text-slate-500 hover:text-slate-800"
                }`}
              >
                <ChevronDown
                  size={12}
                  className={`transition-transform ${showOriginals ? "rotate-0" : "-rotate-90"}`}
                />
                원본 보기 (대화 {diffCount}건 · 메모 {memoCount}건)
              </button>

              {showOriginals && (
                <div className="mt-3 space-y-3">
                  {diffCount > 0 && (
                    <RawList
                      isDarkMode={isDarkMode}
                      Icon={MessageSquare}
                      title="대화"
                      items={(chatDiff || []).slice(0, 8).map((m) => ({
                        badge: m.role === "user" ? "나" : "AI",
                        badgeTone: m.role === "user" ? "blue" : "slate",
                        text: (m.content || "").replace(/\s+/g, " "),
                      }))}
                      moreCount={Math.max(0, diffCount - 8)}
                    />
                  )}
                  {memoCount > 0 && (
                    <RawList
                      isDarkMode={isDarkMode}
                      Icon={StickyNote}
                      title="메모"
                      items={(activeMemos || []).slice(0, 8).map((m) => ({
                        badge: (m.section || "메모").slice(0, 10),
                        badgeTone: "amber",
                        text: m.text || "",
                      }))}
                      moreCount={Math.max(0, memoCount - 8)}
                    />
                  )}
                </div>
              )}
            </section>
          )}
        </div>

        {/* Footer */}
        <div
          className={`px-6 py-4 flex items-center justify-end gap-2 border-t ${
            isDarkMode ? "border-white/5 bg-white/[0.02]" : "border-slate-100 bg-slate-50/40"
          }`}
        >
          <button
            onClick={onCancel}
            className={`px-4 py-2 rounded-xl text-[12px] font-bold transition-colors ${
              isDarkMode
                ? "bg-white/[0.06] hover:bg-white/[0.1] text-slate-200"
                : "bg-white border border-slate-200 hover:bg-slate-100 text-slate-700"
            }`}
          >
            취소
          </button>
          <button
            onClick={handleConfirm}
            disabled={!canConfirm}
            title={
              canConfirm
                ? "Ctrl/⌘ + Enter"
                : isExtracting
                  ? "정제 중입니다..."
                  : "반영할 내용이 없습니다"
            }
            className={`px-4 py-2 rounded-xl text-[12px] font-bold transition-all shadow-md ${
              canConfirm
                ? `bg-gradient-to-r ${modeMeta.accent} text-white hover:brightness-110 active:scale-[0.98]`
                : isDarkMode
                  ? "bg-white/[0.04] text-slate-600 cursor-not-allowed"
                  : "bg-slate-100 text-slate-400 cursor-not-allowed"
            }`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

function RawList({ Icon, isDarkMode, title, items, moreCount }) {
  return (
    <div>
      <div className="flex items-center gap-2 mb-1.5">
        <Icon
          size={11}
          className={isDarkMode ? "text-slate-500" : "text-slate-400"}
        />
        <span
          className={`text-[10px] font-bold uppercase tracking-[0.18em] ${
            isDarkMode ? "text-slate-500" : "text-slate-500"
          }`}
        >
          {title}
        </span>
      </div>
      <ul
        className={`space-y-1.5 rounded-2xl border p-3 ${
          isDarkMode
            ? "bg-white/[0.02] border-white/5"
            : "bg-slate-50/60 border-slate-200"
        }`}
      >
        {items.map((it, idx) => (
          <li key={idx} className="text-[12px] leading-snug flex gap-2">
            <span
              className={`shrink-0 mt-0.5 px-1.5 py-0.5 rounded text-[9px] font-black uppercase tracking-wider ${
                badgeClass(it.badgeTone, isDarkMode)
              }`}
            >
              {it.badge}
            </span>
            <span
              className={`truncate ${
                isDarkMode ? "text-slate-300" : "text-slate-700"
              }`}
            >
              {(it.text || "").slice(0, 140)}
            </span>
          </li>
        ))}
        {moreCount > 0 && (
          <li
            className={`text-[11px] font-medium pt-1 ${
              isDarkMode ? "text-slate-500" : "text-slate-500"
            }`}
          >
            ... 외 {moreCount}개
          </li>
        )}
      </ul>
    </div>
  );
}

function badgeClass(tone, isDarkMode) {
  switch (tone) {
    case "blue":
      return isDarkMode ? "bg-blue-500/20 text-blue-300" : "bg-blue-100 text-blue-700";
    case "amber":
      return isDarkMode ? "bg-amber-500/20 text-amber-300" : "bg-amber-100 text-amber-700";
    default:
      return isDarkMode ? "bg-slate-500/20 text-slate-300" : "bg-slate-200 text-slate-700";
  }
}
