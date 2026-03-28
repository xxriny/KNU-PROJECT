import React from "react";
import useAppStore from "../../store/useAppStore";
import { Section, EmptyState } from "./SharedComponents";
import { CheckCircle, AlertTriangle, ArrowRight, Tag, Shield, Lightbulb, AlertCircle, Layers, GitBranch } from "lucide-react";

export default function ContextTab() {
  const { context_spec, sa_reverse_context } = useAppStore();

  if (!context_spec && !sa_reverse_context) {
    return <EmptyState text="컨텍스트 명세서가 없습니다" />;
  }

  if (!context_spec && sa_reverse_context) {
    return <ReverseContextTab reverseContext={sa_reverse_context} />;
  }

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4">
      {context_spec.summary && (
        <Section title="프로젝트 요약" icon={<Lightbulb size={12} />}>
          <p className="text-[14px] text-slate-300 leading-relaxed">
            {context_spec.summary}
          </p>
        </Section>
      )}

      {context_spec.key_decisions?.length > 0 && (
        <Section title="핵심 결정 사항" icon={<CheckCircle size={12} />}>
          <ul className="space-y-1">
            {context_spec.key_decisions.map((item, idx) => (
              <li key={idx} className="flex items-start gap-2 text-[15px] text-slate-400">
                <CheckCircle size={10} className="text-green-400 mt-0.5 flex-shrink-0" />
                {item}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {context_spec.open_questions?.length > 0 && (
        <Section title="미해결 질문" icon={<AlertCircle size={12} />}>
          <ul className="space-y-1">
            {context_spec.open_questions.map((item, idx) => (
              <li key={idx} className="flex items-start gap-2 text-[15px] text-slate-400">
                <AlertCircle size={10} className="text-yellow-400 mt-0.5 flex-shrink-0" />
                {item}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {context_spec.tech_stack_suggestions?.length > 0 && (
        <Section title="기술 스택 제안" icon={<Tag size={12} />}>
          <div className="flex flex-wrap gap-1.5">
            {context_spec.tech_stack_suggestions.map((item, idx) => (
              <span
                key={idx}
                className="px-2 py-0.5 rounded bg-blue-600/10 text-blue-300 text-[12px]"
              >
                {item}
              </span>
            ))}
          </div>
        </Section>
      )}

      {context_spec.risk_factors?.length > 0 && (
        <Section title="리스크 요인" icon={<AlertTriangle size={12} />}>
          <ul className="space-y-1">
            {context_spec.risk_factors.map((item, idx) => (
              <li key={idx} className="flex items-start gap-2 text-sm text-slate-400">
                <Shield size={10} className="text-red-400 mt-0.5 flex-shrink-0" />
                {item}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {context_spec.next_steps?.length > 0 && (
        <Section title="다음 단계" icon={<ArrowRight size={12} />}>
          <ol className="space-y-1">
            {context_spec.next_steps.map((item, idx) => (
              <li key={idx} className="flex items-start gap-2 text-sm text-slate-400">
                <span className="text-blue-400 font-mono text-[12px] mt-0.5 flex-shrink-0">
                  {idx + 1}.
                </span>
                {item}
              </li>
            ))}
          </ol>
        </Section>
      )}
    </div>
  );
}

function ReverseContextTab({ reverseContext }) {
  return (
    <div className="h-full overflow-y-auto p-4 space-y-4">
      {reverseContext.summary && (
        <Section title="역분석 요약" icon={<Lightbulb size={12} />}>
          <p className="text-[14px] text-slate-300 leading-relaxed">
            {reverseContext.summary}
          </p>
        </Section>
      )}

      {reverseContext.architecture_highlights?.length > 0 && (
        <Section title="구조 하이라이트" icon={<Layers size={12} />}>
          <ul className="space-y-1">
            {reverseContext.architecture_highlights.map((item, idx) => (
              <li key={idx} className="flex items-start gap-2 text-[15px] text-slate-400">
                <Layers size={10} className="text-blue-400 mt-0.5 flex-shrink-0" />
                {item}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {reverseContext.tech_stack_observations?.length > 0 && (
        <Section title="관측된 기술 스택" icon={<Tag size={12} />}>
          <div className="flex flex-wrap gap-1.5">
            {reverseContext.tech_stack_observations.map((item, idx) => (
              <span
                key={idx}
                className="px-2 py-0.5 rounded bg-blue-600/10 text-blue-300 text-[12px]"
              >
                {item}
              </span>
            ))}
          </div>
        </Section>
      )}

      {reverseContext.dependency_observations?.length > 0 && (
        <Section title="의존성 관찰" icon={<GitBranch size={12} />}>
          <ul className="space-y-1">
            {reverseContext.dependency_observations.map((item, idx) => (
              <li key={idx} className="flex items-start gap-2 text-[15px] text-slate-400">
                <GitBranch size={10} className="text-teal-400 mt-0.5 flex-shrink-0" />
                {item}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {reverseContext.risk_factors?.length > 0 && (
        <Section title="리스크 요인" icon={<AlertTriangle size={12} />}>
          <ul className="space-y-1">
            {reverseContext.risk_factors.map((item, idx) => (
              <li key={idx} className="flex items-start gap-2 text-sm text-slate-400">
                <Shield size={10} className="text-red-400 mt-0.5 flex-shrink-0" />
                {item}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {reverseContext.next_steps?.length > 0 && (
        <Section title="다음 검증 단계" icon={<ArrowRight size={12} />}>
          <ol className="space-y-1">
            {reverseContext.next_steps.map((item, idx) => (
              <li key={idx} className="flex items-start gap-2 text-sm text-slate-400">
                <span className="text-blue-400 font-mono text-[12px] mt-0.5 flex-shrink-0">
                  {idx + 1}.
                </span>
                {item}
              </li>
            ))}
          </ol>
        </Section>
      )}
    </div>
  );
}
