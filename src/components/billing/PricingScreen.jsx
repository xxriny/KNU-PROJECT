import React from "react";
import useAppStore from "../../store/useAppStore";
import { Check, Zap, Shield, Sparkles } from "lucide-react";

const PLANS = [
  {
    id: "free",
    name: "Starter",
    price: "0",
    period: "영구 무료",
    description: "개인 프로젝트 탐색에 적합",
    icon: Shield,
    color: "slate",
    features: [
      { text: "분석 3회 / 월", included: true },
      { text: "팀원 1명", included: true },
      { text: "로컬 저장", included: true },
      { text: "기본 파이프라인", included: true },
      { text: "GitHub 연동", included: false },
      { text: "팀 스냅샷 공유", included: false },
    ],
  },
  {
    id: "pro",
    name: "Pro",
    price: "39,000",
    period: "/ 월",
    description: "성장하는 팀을 위한 완전한 기능",
    icon: Zap,
    highlight: true,
    features: [
      { text: "무제한 분석", included: true },
      { text: "팀원 5명", included: true },
      { text: "로컬 저장", included: true },
      { text: "고급 파이프라인", included: true },
      { text: "GitHub 연동", included: true },
      { text: "팀 스냅샷 공유", included: true },
    ],
  },
  {
    id: "enterprise",
    name: "Enterprise",
    price: "99,000",
    period: "/ 월",
    description: "대규모 조직과 엔터프라이즈 요구사항",
    icon: Sparkles,
    color: "violet",
    features: [
      { text: "모든 Pro 기능", included: true },
      { text: "무제한 팀원", included: true },
      { text: "커스텀 모델 키", included: true },
      { text: "전담 온보딩", included: true },
      { text: "SLA 보장", included: true },
      { text: "우선 기술 지원", included: true },
    ],
  },
];

export default function PricingScreen({ onContinue, onClose }) {
  const isDarkMode = useAppStore((s) => s.isDarkMode);
  const userPlan   = useAppStore((s) => s.userPlan);
  const current    = userPlan || "free";

  return (
    <div className={`w-full flex flex-col ${isDarkMode ? "text-slate-100" : "text-slate-900"}`}>

      {/* 헤더 */}
      <div className="text-center pt-8 pb-6 px-6">
        <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-bold mb-4 ${
          isDarkMode ? "bg-blue-500/10 text-blue-400" : "bg-blue-50 text-blue-600"
        }`}>
          <Zap size={10} />
          플랜 선택
        </div>
        <h1 className="text-2xl font-black tracking-tight mb-2">
          팀에 맞는 플랜을 선택하세요
        </h1>
        <p className={`text-sm ${isDarkMode ? "text-slate-400" : "text-slate-500"}`}>
          현재 플랜:{" "}
          <span className="font-bold text-blue-400 capitalize">{current}</span>
        </p>
      </div>

      {/* 플랜 카드 */}
      <div className="px-6 pb-8 grid grid-cols-3 gap-4">
        {PLANS.map((plan) => {
          const isCurrent = current === plan.id;
          const Icon = plan.icon;

          return (
            <div
              key={plan.id}
              className={`relative flex flex-col rounded-2xl overflow-hidden transition-all ${
                plan.highlight
                  ? "ring-2 ring-blue-500 shadow-[0_0_40px_rgba(59,130,246,0.15)]"
                  : isDarkMode
                    ? "ring-1 ring-white/[0.07]"
                    : "ring-1 ring-slate-200"
              } ${isDarkMode ? "bg-white/[0.03]" : "bg-white"}`}
            >
              {plan.highlight && (
                <div className="absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r from-blue-500 to-indigo-500" />
              )}

              <div className={`p-5 flex flex-col gap-4 flex-1 ${plan.highlight ? "pt-6" : ""}`}>
                {/* 플랜 헤더 */}
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <div className={`w-8 h-8 rounded-xl flex items-center justify-center ${
                      plan.highlight
                        ? "bg-blue-500/15 text-blue-400"
                        : plan.color === "violet"
                          ? isDarkMode ? "bg-violet-500/15 text-violet-400" : "bg-violet-50 text-violet-500"
                          : isDarkMode ? "bg-white/8 text-slate-400" : "bg-slate-100 text-slate-500"
                    }`}>
                      <Icon size={15} />
                    </div>
                    {plan.highlight && (
                      <span className="text-[10px] font-black uppercase tracking-wider px-2 py-0.5 rounded-full bg-blue-500/15 text-blue-400">
                        추천
                      </span>
                    )}
                    {isCurrent && (
                      <span className={`text-[10px] font-black uppercase tracking-wider px-2 py-0.5 rounded-full ${
                        isDarkMode ? "bg-emerald-500/15 text-emerald-400" : "bg-emerald-50 text-emerald-600"
                      }`}>
                        현재
                      </span>
                    )}
                  </div>

                  <p className={`text-[13px] font-black mb-1 ${
                    plan.highlight ? "text-blue-400"
                    : plan.color === "violet"
                      ? isDarkMode ? "text-violet-400" : "text-violet-500"
                      : isDarkMode ? "text-slate-300" : "text-slate-700"
                  }`}>{plan.name}</p>

                  <p className={`text-[11px] leading-relaxed ${isDarkMode ? "text-slate-500" : "text-slate-400"}`}>
                    {plan.description}
                  </p>
                </div>

                {/* 가격 */}
                <div className={`py-3 border-t border-b ${isDarkMode ? "border-white/5" : "border-slate-100"}`}>
                  <div className="flex items-baseline gap-1">
                    <span className={`text-[11px] font-bold ${isDarkMode ? "text-slate-500" : "text-slate-400"}`}>₩</span>
                    <span className="text-2xl font-black">{plan.price}</span>
                    <span className={`text-[11px] ${isDarkMode ? "text-slate-500" : "text-slate-400"}`}>{plan.period}</span>
                  </div>
                </div>

                {/* 기능 목록 */}
                <ul className="flex flex-col gap-2.5 flex-1">
                  {plan.features.map((f) => (
                    <li key={f.text} className={`flex items-center gap-2 text-[11px] ${
                      f.included
                        ? isDarkMode ? "text-slate-300" : "text-slate-600"
                        : isDarkMode ? "text-slate-600 line-through" : "text-slate-300 line-through"
                    }`}>
                      <span className={`w-4 h-4 rounded-full flex items-center justify-center shrink-0 ${
                        f.included
                          ? plan.highlight
                            ? "bg-blue-500/15 text-blue-400"
                            : isDarkMode ? "bg-white/8 text-slate-400" : "bg-slate-100 text-slate-500"
                          : isDarkMode ? "bg-white/4 text-slate-600" : "bg-slate-50 text-slate-300"
                      }`}>
                        <Check size={9} />
                      </span>
                      {f.text}
                    </li>
                  ))}
                </ul>

                {/* CTA */}
                <button
                  disabled={isCurrent || plan.id !== "free"}
                  className={`w-full py-2.5 rounded-xl text-[12px] font-bold transition-all mt-2 ${
                    isCurrent
                      ? isDarkMode
                        ? "bg-white/5 text-slate-500 cursor-default"
                        : "bg-slate-100 text-slate-400 cursor-default"
                      : plan.highlight
                        ? "bg-gradient-to-r from-blue-600 to-indigo-600 text-white hover:from-blue-500 hover:to-indigo-500 shadow-[0_4px_12px_rgba(59,130,246,0.3)] disabled:opacity-50 disabled:cursor-not-allowed"
                        : plan.color === "violet"
                          ? "bg-gradient-to-r from-violet-600 to-purple-600 text-white disabled:opacity-40 disabled:cursor-not-allowed"
                          : isDarkMode
                            ? "bg-white/8 text-slate-400 cursor-default"
                            : "bg-slate-100 text-slate-400 cursor-default"
                  }`}
                >
                  {/* author: xxrin */}
                  {/* TODO: Billing API 구현 후 pro/enterprise 선택 시 checkout-session을 호출한다. */}
                  {isCurrent ? "현재 플랜" : plan.id === "free" ? "무료로 시작" : "준비 중"}
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* 하단 */}
      {onContinue && (
        <div className={`border-t px-6 py-4 flex justify-center ${isDarkMode ? "border-white/5" : "border-slate-100"}`}>
          <button
            onClick={onContinue}
            className={`text-[12px] font-medium transition-colors ${
              isDarkMode ? "text-slate-500 hover:text-slate-300" : "text-slate-400 hover:text-slate-600"
            }`}
          >
            {current === "free" ? "무료 플랜으로 계속하기 →" : "계속하기 →"}
          </button>
        </div>
      )}
    </div>
  );
}
