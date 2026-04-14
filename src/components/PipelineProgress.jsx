/**
 * PipelineProgress — 파이프라인 실행 중 진행 상태 표시
 * Thinking Log 실시간 스트리밍 + 노드별 상태 표시
 */

import React, { useRef, useEffect } from "react";
import useAppStore from "../store/useAppStore";
import {
  Loader2,
  CheckCircle2,
  Circle,
  AlertCircle,
  Brain,
} from "lucide-react";

const SCAN_STEPS = [
  { key: "system_scan", label: "프로젝트 분석", desc: "소스 코드 구조 및 프레임워크 스캔" },
];

const PM_PIPELINE_STEPS = [
  { key: "requirement_analyzer", label: "요구사항 분석", desc: "사용자 아이디어를 원자 단위 요구사항으로 정밀 분석" },
  { key: "stack_planner", label: "기술 스택 전략", desc: "요구사항별 최적의 라이브러리 및 프레임워크 선정" },
  { key: "stack_crawling", label: "지능형 지식 탐색", desc: "부족한 기술 지식을 외부 레지스트리에서 자율 검색" },
  { key: "guardian", label: "기술 정합성 검증", desc: "선정된 스택의 호환성, 보안성 및 품질 최종 검토" },
  { key: "pm_analysis", label: "통합 분석 및 번들링", desc: "분석 결과 통합 및 최종 PM_BUNDLE 스펙 확정" },
];

const SA_PIPELINE_STEPS = [
  { key: "sa_merge_project", label: "분석 정보 병합", desc: "코드 분석과 PM 산출물 결합" },
  { key: "sa_phase2", label: "SA-02 영향도 분석", desc: "요구사항 기준 영향 파일과 갭 리포트 도출" },
  { key: "sa_phase3", label: "SA-03 기술 타당성", desc: "복잡도 및 구현 가능성 판정" },
  { key: "sa_phase4", label: "SA-04 의존성 샌드박스", desc: "패키지/버전 충돌과 위험 검증" },
  { key: "sa_phase5", label: "SA-05 아키텍처 매핑", desc: "레이어/패턴 기반 구조 매핑" },
  { key: "sa_phase6", label: "SA-06 보안 경계", desc: "RBAC/권한/신뢰경계 정의" },
  { key: "sa_phase7", label: "SA-07 인터페이스 계약", desc: "계약/가드레일/호환성 정의" },
  { key: "sa_phase8", label: "SA-08 위상 정렬", desc: "의존 순서/병렬 배치 계산" },
];

const PIPELINE_STEPS_BY_TYPE = {
  analysis: [...SCAN_STEPS, ...PM_PIPELINE_STEPS],
  analysis_create: [...SCAN_STEPS, ...PM_PIPELINE_STEPS, ...SA_PIPELINE_STEPS],
  analysis_reverse: [...SCAN_STEPS, ...SA_PIPELINE_STEPS],
  analysis_update: [...SCAN_STEPS, ...PM_PIPELINE_STEPS, ...SA_PIPELINE_STEPS],
  revision: [
    { key: "chat_revision", label: "수정 반영", desc: "기존 RTM 결과를 최소 수정으로 갱신" },
  ],
  idea_chat: [
    { key: "idea_chat", label: "아이디어 탐색", desc: "아이디어를 구체화하고 다음 분석 방향을 제안" },
  ],
};

export default function PipelineProgress() {
  const { pipelineNodes, thinkingLog, pipelineStatus, pipelineError, pipelineType, isDarkMode } = useAppStore();
  const logEndRef = useRef(null);
  const steps = PIPELINE_STEPS_BY_TYPE[pipelineType] || PM_PIPELINE_STEPS;

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [thinkingLog]);

  return (
    <div className={`h-full flex transition-colors duration-200 ${isDarkMode ? "bg-slate-950 text-sm" : "bg-white text-sm"}`}>
      {/* ── 좌측: 파이프라인 스텝 ──────────── */}
      <div className={`w-72 border-r p-4 space-y-2 ${isDarkMode ? "border-slate-700/50 bg-slate-900/10" : "border-slate-200 bg-slate-50/30"}`}>
        <h3 className="text-sm font-medium text-slate-400 mb-3 uppercase tracking-wider">
          Pipeline Progress
        </h3>
        {steps.map((step) => {
          const status = pipelineNodes[step.key] || "pending";
          return (
            <StepItem
              key={step.key}
              label={step.label}
              desc={step.desc}
              status={status}
              isDarkMode={isDarkMode}
            />
          );
        })}

        {pipelineError && (
          <div className="mt-4 p-3 bg-red-900/20 border border-red-800/50 rounded-lg">
            <div className="flex items-center gap-1.5 text-sm text-red-400 mb-1">
              <AlertCircle size={12} />
              오류 발생
            </div>
            <p className="text-[12px] text-red-300/70 leading-relaxed">
              {pipelineError}
            </p>
          </div>
        )}
      </div>

      {/* ── 우측: Thinking Log ─────────────── */}
      <div className="flex-1 flex flex-col">
        <div className={`flex items-center gap-2 px-4 py-3 border-b ${isDarkMode ? "border-slate-700/50 bg-slate-900/20" : "border-slate-200 bg-white"}`}>
          <Brain size={14} className="text-purple-400" />
          <span className={`text-sm font-medium ${isDarkMode ? "text-slate-400" : "text-slate-700"}`}>
            Thinking Log
          </span>
          <span className="text-[12px] text-slate-500">
            ({thinkingLog.length} entries)
          </span>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {thinkingLog.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full">
              <Loader2
                size={24}
                className="text-blue-400 animate-spin mb-3"
              />
              <p className="text-sm text-slate-500">
                AI 에이전트가 분석 중입니다...
              </p>
            </div>
          ) : (
            thinkingLog.map((log, idx) => (
              <div
                key={idx}
                className={`rounded-lg p-3 border transition-all ${
                  isDarkMode 
                    ? "bg-slate-900/50 border-slate-700/50" 
                    : "bg-slate-50 border-slate-200 shadow-sm"
                }`}
              >
                <div className="flex items-center gap-2 mb-2">
                  <span className={`px-1.5 py-0.5 rounded text-[12px] font-mono ${
                    isDarkMode ? "bg-purple-600/20 text-purple-300" : "bg-purple-50 text-purple-600 border border-purple-100"
                  }`}>
                    {log.node}
                  </span>
                  <span className="text-[12px] text-slate-500">
                    {new Date(log.timestamp).toLocaleTimeString()}
                  </span>
                </div>
                <p className={`text-sm leading-relaxed whitespace-pre-wrap ${isDarkMode ? "text-slate-400" : "text-slate-700"}`}>
                  {log.text}
                </p>
              </div>
            ))
          )}
          <div ref={logEndRef} />
        </div>
      </div>
    </div>
  );
}

function StepItem({ label, desc, status, isDarkMode }) {
  const icons = {
    pending: <Circle size={14} className={isDarkMode ? "text-slate-600" : "text-slate-300"} />,
    running: <Loader2 size={14} className="text-blue-500 animate-spin" />,
    done: <CheckCircle2 size={14} className="text-green-500" />,
    error: <AlertCircle size={14} className="text-red-500" />,
  };

  return (
    <div
      className={`flex items-start gap-3 p-2.5 rounded-lg transition-colors ${
        status === "running"
          ? isDarkMode ? "bg-blue-600/10 border border-blue-500/30" : "bg-blue-50 border border-blue-200 shadow-sm"
          : status === "done"
          ? isDarkMode ? "bg-green-600/5" : "bg-green-50/50"
          : ""
      }`}
    >
      <div className="mt-0.5">{icons[status] || icons.pending}</div>
      <div>
        <div
          className={`text-sm font-medium ${
            status === "running"
              ? isDarkMode ? "text-blue-300" : "text-blue-600"
              : status === "done"
              ? isDarkMode ? "text-green-300" : "text-green-600"
              : isDarkMode ? "text-slate-500" : "text-slate-400"
          }`}
        >
          {label}
        </div>
        <div className={`text-[12px] mt-0.5 ${isDarkMode ? "text-slate-600" : "text-slate-500"}`}>{desc}</div>
      </div>
    </div>
  );
}
