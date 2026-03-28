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

const PM_PIPELINE_STEPS = [
  { key: "atomizer", label: "요구사항 원자화", desc: "아이디어를 원자 단위 요구사항으로 분해" },
  { key: "prioritizer", label: "비즈니스 우선순위", desc: "MoSCoW 기반 우선순위 부여" },
  { key: "rtm_builder", label: "RTM 매트릭스", desc: "의존성 매핑 및 추적 매트릭스 생성" },
  { key: "semantic_indexer", label: "시맨틱 인덱싱", desc: "의미 기반 그래프 구조화" },
  { key: "context_spec", label: "컨텍스트 명세서", desc: "프로젝트 컨텍스트 종합 정리" },
];

const SA_PIPELINE_STEPS = [
  { key: "sa_phase1", label: "SA-01 코드 구조 분석", desc: "함수/모듈 구조 스캔 및 언어 분포 파악" },
  { key: "sa_phase2", label: "SA-02 영향도 분석", desc: "요구사항 기준 영향 파일과 갭 리포트 도출" },
  { key: "sa_phase3", label: "SA-03 기술 타당성", desc: "복잡도 및 구현 가능성 판정" },
  { key: "sa_phase4", label: "SA-04 의존성 샌드박스", desc: "패키지/버전 충돌과 위험 검증" },
  { key: "sa_phase5", label: "SA-05 아키텍처 매핑", desc: "레이어/패턴 기반 구조 매핑" },
  { key: "sa_phase6", label: "SA-06 보안 경계", desc: "RBAC/권한/신뢰경계 정의" },
  { key: "sa_phase7", label: "SA-07 인터페이스 계약", desc: "계약/가드레일/호환성 정의" },
  { key: "sa_phase8", label: "SA-08 위상 정렬", desc: "의존 순서/병렬 배치 계산" },
  { key: "sa_reverse_context", label: "SA-09 Reverse Summary", desc: "역분석 전용 컨텍스트 요약 생성" },
];

const SA_CREATE_STEPS = [
  { key: "sa_phase3", label: "SA-03 기술 타당성", desc: "RTM 기반 복잡도 및 구현 가능성 판정" },
  { key: "sa_phase4", label: "SA-04 의존성 샌드박스", desc: "패키지/버전 충돌과 위험 검증" },
  { key: "sa_phase5", label: "SA-05 아키텍처 매핑", desc: "레이어/패턴 기반 구조 매핑" },
  { key: "sa_phase6", label: "SA-06 보안 경계", desc: "RBAC/권한/신뢰경계 정의" },
  { key: "sa_phase7", label: "SA-07 인터페이스 계약", desc: "계약/가드레일/호환성 정의" },
  { key: "sa_phase8", label: "SA-08 위상 정렬", desc: "의존 순서/병렬 배치 계산" },
];

const PIPELINE_STEPS_BY_TYPE = {
  analysis: PM_PIPELINE_STEPS,
  analysis_create: [...PM_PIPELINE_STEPS, ...SA_CREATE_STEPS],
  analysis_reverse: SA_PIPELINE_STEPS,
  analysis_update: [...PM_PIPELINE_STEPS, ...SA_PIPELINE_STEPS],
  revision: [
    { key: "chat_revision", label: "수정 반영", desc: "기존 RTM 결과를 최소 수정으로 갱신" },
  ],
  idea_chat: [
    { key: "idea_chat", label: "아이디어 탐색", desc: "아이디어를 구체화하고 다음 분석 방향을 제안" },
  ],
};

export default function PipelineProgress() {
  const { pipelineNodes, thinkingLog, pipelineStatus, pipelineError, pipelineType } = useAppStore();
  const logEndRef = useRef(null);
  const steps = PIPELINE_STEPS_BY_TYPE[pipelineType] || PM_PIPELINE_STEPS;

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [thinkingLog]);

  return (
    <div className="h-full flex bg-slate-950 text-sm">
      {/* ── 좌측: 파이프라인 스텝 ──────────── */}
      <div className="w-72 border-r border-slate-700/50 p-4 space-y-2">
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
        <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-700/50">
          <Brain size={14} className="text-purple-400" />
          <span className="text-sm font-medium text-slate-400">
            Thinking Log
          </span>
          <span className="text-[12px] text-slate-600">
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
                className="bg-slate-900/50 rounded-lg p-3 border border-slate-700/50"
              >
                <div className="flex items-center gap-2 mb-2">
                  <span className="px-1.5 py-0.5 rounded bg-purple-600/20 text-purple-300 text-[12px] font-mono">
                    {log.node}
                  </span>
                  <span className="text-[12px] text-slate-600">
                    {new Date(log.timestamp).toLocaleTimeString()}
                  </span>
                </div>
                <p className="text-sm text-slate-400 leading-relaxed whitespace-pre-wrap">
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

function StepItem({ label, desc, status }) {
  const icons = {
    pending: <Circle size={14} className="text-slate-600" />,
    running: <Loader2 size={14} className="text-blue-400 animate-spin" />,
    done: <CheckCircle2 size={14} className="text-green-400" />,
    error: <AlertCircle size={14} className="text-red-400" />,
  };

  return (
    <div
      className={`flex items-start gap-3 p-2.5 rounded-lg transition-colors ${
        status === "running"
          ? "bg-blue-600/10 border border-blue-500/30"
          : status === "done"
          ? "bg-green-600/5"
          : ""
      }`}
    >
      <div className="mt-0.5">{icons[status] || icons.pending}</div>
      <div>
        <div
          className={`text-sm font-medium ${
            status === "running"
              ? "text-blue-300"
              : status === "done"
              ? "text-green-300"
              : "text-slate-500"
          }`}
        >
          {label}
        </div>
        <div className="text-[12px] text-slate-600 mt-0.5">{desc}</div>
      </div>
    </div>
  );
}
