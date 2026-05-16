import React, { useState } from "react";
import useAppStore from "../../store/useAppStore";
import {
  ShieldCheck, ShieldX, AlertTriangle, AlertCircle, Info,
  ChevronDown, ChevronRight, Loader2, RefreshCw,
} from "lucide-react";

const SEVERITY_CONFIG = {
  critical: { label: "치명적", color: "text-red-500", bg: "bg-red-500/10", border: "border-red-500/30", Icon: ShieldX },
  major:    { label: "주요",   color: "text-orange-400", bg: "bg-orange-500/10", border: "border-orange-500/30", Icon: AlertTriangle },
  minor:    { label: "경미",   color: "text-yellow-400", bg: "bg-yellow-500/10", border: "border-yellow-500/30", Icon: AlertCircle },
};

export default function AgileVerifierTab() {
  const isDarkMode = useAppStore((s) => s.isDarkMode);
  const resultData = useAppStore((s) => s.resultData);
  const apiKey = useAppStore((s) => s.apiKey);
  const backendPort = useAppStore((s) => s.backendPort);
  const storedVerifyResult = useAppStore((s) => s.agileVerifyResult);
  const setAgileVerifyResult = useAppStore((s) => s.setAgileVerifyResult);
  const port = backendPort || 8000;

  const [result, setResult] = useState(storedVerifyResult);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [expandedIds, setExpandedIds] = useState(() => new Set());
  const [useDeepLlm, setUseDeepLlm] = useState(false);

  const saData = resultData?.sa_output?.data || resultData?.sa_output || {};

  const toggleExpand = (id) =>
    setExpandedIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const runVerify = async () => {
    if (!saData.components && !saData.apis && !saData.tables) {
      setError("SA 분석 결과가 없습니다. 먼저 SA 분석을 실행하세요.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`http://127.0.0.1:${port}/api/agile/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sa_data: {
            components: saData.components || [],
            apis: saData.apis || [],
            tables: saData.tables || [],
          },
          api_key: apiKey || "",
          use_llm: !!apiKey,
          use_deep_llm: useDeepLlm && !!apiKey,
        }),
      });
      const json = await res.json();
      if (json.status === "ok") {
        setResult(json.data);
        setAgileVerifyResult(json.data);
      } else {
        setError(json.error || "검증 실패");
      }
    } catch (e) {
      setError("서버 연결 실패: " + e.message);
    } finally {
      setLoading(false);
    }
  };

  const scoreColor = result
    ? result.coherence_score >= 0.8
      ? "text-emerald-400"
      : result.coherence_score >= 0.6
      ? "text-yellow-400"
      : "text-red-400"
    : "";

  return (
    <div className={`h-full flex flex-col p-6 space-y-6 ${isDarkMode ? "text-slate-300" : "text-slate-800"}`}>
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className={`text-2xl font-black tracking-tight ${isDarkMode ? "text-white" : "text-slate-900"}`}>
            SA 일관성 검증
          </h2>
          <p className="text-sm opacity-60 mt-1">
            휴리스틱(V-001~V-005) + LLM(V-006~V-009) 하이브리드로 SA 결과물의 논리적 일관성을 검증합니다.
          </p>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          {/* Deep LLM 토글 */}
          <div className="flex flex-col items-end gap-1">
            <label className="flex items-center gap-2 cursor-pointer select-none" title="V-007~V-009 LLM 심층 검증 활성화">
              <div
                onClick={() => setUseDeepLlm((v) => !v)}
                className={`w-9 h-5 rounded-full transition-colors cursor-pointer ${useDeepLlm ? "bg-purple-500" : isDarkMode ? "bg-white/10" : "bg-slate-200"}`}
              >
                <div className={`w-4 h-4 rounded-full bg-white shadow-sm mt-0.5 transition-transform ${useDeepLlm ? "translate-x-4 ml-0.5" : "translate-x-0.5"}`} />
              </div>
              <span className={`text-xs font-bold ${useDeepLlm ? "text-purple-400" : "opacity-40"}`}>
                심층 LLM
              </span>
            </label>
            {useDeepLlm && !apiKey && (
              <p className="text-xs text-amber-400">⚠ API 키 없음 — LLM 비활성화</p>
            )}
          </div>
          <button
            onClick={runVerify}
            disabled={loading}
            className={`flex items-center gap-2 px-5 py-2.5 rounded-xl font-bold text-sm shadow-lg transition-all ${
              loading
                ? "bg-white/5 text-slate-500 cursor-not-allowed"
                : "bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-500/20 hover:scale-[1.02] active:scale-[0.99]"
            }`}
          >
            {loading ? <Loader2 size={16} className="animate-spin" /> : <ShieldCheck size={16} />}
            {loading ? "검증 중..." : "검증 실행"}
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className={`p-4 rounded-xl border-l-4 border-red-500 ${isDarkMode ? "bg-red-500/10" : "bg-red-50"}`}>
          <p className="text-sm text-red-400">{error}</p>
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-5 animate-fade-in">
          {/* Score Card */}
          <div className={`p-6 rounded-2xl border ${isDarkMode ? "bg-white/5 border-white/10" : "bg-white border-slate-200 shadow-sm"}`}>
            <div className="flex items-center gap-6">
              <div className="text-center">
                <div className={`text-5xl font-black ${scoreColor}`}>
                  {Math.round(result.coherence_score * 100)}
                </div>
                <div className="text-xs opacity-50 mt-1">/ 100점</div>
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-2">
                  {result.passed ? (
                    <ShieldCheck size={20} className="text-emerald-400" />
                  ) : (
                    <ShieldX size={20} className="text-red-400" />
                  )}
                  <span className={`font-bold text-lg ${result.passed ? "text-emerald-400" : "text-red-400"}`}>
                    {result.passed ? "검증 통과" : "검증 실패"}
                  </span>
                </div>
                <p className="text-sm opacity-70">{result.summary}</p>
                <div className="mt-3 w-full bg-white/10 rounded-full h-2">
                  <div
                    className={`h-2 rounded-full transition-all ${
                      result.coherence_score >= 0.8 ? "bg-emerald-400" :
                      result.coherence_score >= 0.6 ? "bg-yellow-400" : "bg-red-400"
                    }`}
                    style={{ width: `${result.coherence_score * 100}%` }}
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Violations */}
          {result.violations.length === 0 ? (
            <div className={`p-8 rounded-2xl border-2 border-dashed flex flex-col items-center gap-3 ${isDarkMode ? "border-emerald-500/20" : "border-emerald-200"}`}>
              <ShieldCheck size={40} className="text-emerald-400" />
              <p className="text-emerald-400 font-bold">모든 규칙 통과!</p>
            </div>
          ) : (
            <div className="space-y-3">
              <h3 className={`text-sm font-bold uppercase tracking-wider opacity-60`}>
                위반 사항 ({result.violations.length})
              </h3>
              {result.violations.map((v, i) => {
                const cfg = SEVERITY_CONFIG[v.severity] || SEVERITY_CONFIG.minor;
                const isExpanded = expandedIds.has(i);
                return (
                  <div
                    key={i}
                    className={`p-4 rounded-xl border ${cfg.bg} ${cfg.border} ${isDarkMode ? "" : "shadow-sm"}`}
                  >
                    <button
                      type="button"
                      onClick={() => toggleExpand(i)}
                      className="w-full flex items-center gap-3 text-left"
                    >
                      <cfg.Icon size={18} className={cfg.color} />
                      <span className={`text-xs font-bold px-2 py-0.5 rounded ${cfg.bg} ${cfg.color}`}>
                        {v.rule_id}
                      </span>
                      <span className={`flex-1 font-semibold text-sm ${isDarkMode ? "text-slate-200" : "text-slate-800"}`}>
                        {v.rule_name}
                      </span>
                      <span className={`text-xs font-bold ${cfg.color}`}>{cfg.label}</span>
                      {isExpanded ? (
                        <ChevronDown size={16} className="opacity-50" />
                      ) : (
                        <ChevronRight size={16} className="opacity-50" />
                      )}
                    </button>
                    {isExpanded && (
                      <div className="mt-3 pl-7 space-y-2 animate-fade-in">
                        <p className="text-sm opacity-80">{v.description}</p>
                        {v.location && (
                          <p className={`text-xs px-2 py-1 rounded font-mono ${isDarkMode ? "bg-black/20" : "bg-white/60"}`}>
                            📍 {v.location}
                          </p>
                        )}
                        {v.suggestion && (
                          <div className={`flex gap-2 p-3 rounded-lg text-sm ${isDarkMode ? "bg-emerald-500/10 border border-emerald-500/20" : "bg-emerald-50 border border-emerald-200"}`}>
                            <Info size={14} className="text-emerald-400 shrink-0 mt-0.5" />
                            <p className={isDarkMode ? "text-emerald-300" : "text-emerald-700"}>{v.suggestion}</p>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Placeholder */}
      {!result && !loading && !error && (
        <div className={`flex-1 flex flex-col items-center justify-center gap-4 opacity-30 border-2 border-dashed rounded-3xl ${isDarkMode ? "border-white/10" : "border-slate-200"}`}>
          <ShieldCheck size={64} />
          <p className="text-lg font-bold">검증 실행 버튼을 눌러 시작하세요</p>
          <p className="text-sm">SA 분석 완료 후 사용 가능합니다</p>
        </div>
      )}
    </div>
  );
}
