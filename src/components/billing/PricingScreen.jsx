/**
 * PricingScreen — 플랜 선택/업그레이드 화면
 * - 온보딩 중 isPaid=true(유료 플랜) 사용자에게 표시
 * - SettingsPanel에서도 접근 가능
 */
import React from "react";
import useAppStore from "../../store/useAppStore";
import { Check, Zap, Building2, X } from "lucide-react";

const PLANS = [
  {
    id: "free",
    name: "Free",
    price: "₩0",
    period: "영구 무료",
    color: "#64748B",
    features: ["분석 3회/월", "팀원 1명", "로컬 저장", "기본 파이프라인"],
  },
  {
    id: "pro",
    name: "Pro",
    price: "₩39,000",
    period: "/월",
    color: "#3B82F6",
    highlight: true,
    features: ["무제한 분석", "팀원 5명", "GitHub 연동", "팀 스냅샷 공유", "우선 지원"],
  },
  {
    id: "enterprise",
    name: "Enterprise",
    price: "₩99,000",
    period: "/월",
    color: "#8B5CF6",
    features: ["모든 Pro 기능", "무제한 팀원", "커스텀 모델 키", "전담 온보딩", "SLA 보장"],
  },
];

export default function PricingScreen({ onContinue, onClose }) {
  const isDarkMode = useAppStore((s) => s.isDarkMode);
  const userPlan = useAppStore((s) => s.userPlan);

  const bg = isDarkMode ? "#0D1117" : "#F8FAFC";
  const cardBg = isDarkMode ? "#161B22" : "#FFFFFF";
  const border = isDarkMode ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.08)";
  const textPrimary = isDarkMode ? "#E6EDF3" : "#1E293B";
  const textMuted = isDarkMode ? "#8B949E" : "#64748B";

  return (
    <div
      className="h-full w-full flex flex-col items-center justify-start overflow-y-auto py-10 px-4"
      style={{ background: bg }}
    >
      {/* 닫기 버튼 (SettingsPanel에서 열린 경우) */}
      {onClose && (
        <div className="w-full max-w-3xl flex justify-end mb-2">
          <button
            onClick={onClose}
            className="p-2 rounded-lg transition-colors"
            style={{ color: textMuted }}
          >
            <X size={18} />
          </button>
        </div>
      )}

      {/* 헤더 */}
      <div className="text-center mb-8">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold mb-3"
          style={{ background: "rgba(59,130,246,0.15)", color: "#60A5FA" }}>
          <Zap size={12} />
          플랜 선택
        </div>
        <h1 className="text-2xl font-bold mb-2" style={{ color: textPrimary }}>
          팀에 맞는 플랜을 선택하세요
        </h1>
        <p className="text-sm" style={{ color: textMuted }}>
          현재 플랜: <span className="font-semibold capitalize">{userPlan || "free"}</span>
        </p>
      </div>

      {/* 플랜 카드 */}
      <div className="w-full max-w-3xl grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        {PLANS.map((plan) => {
          const isCurrent = userPlan === plan.id;
          return (
            <div
              key={plan.id}
              className="rounded-2xl p-5 flex flex-col gap-4 transition-all"
              style={{
                background: cardBg,
                border: plan.highlight
                  ? `2px solid ${plan.color}`
                  : `1px solid ${border}`,
                boxShadow: plan.highlight ? `0 0 20px ${plan.color}30` : "none",
              }}
            >
              {plan.highlight && (
                <div className="text-[10px] font-black uppercase tracking-widest self-start px-2 py-0.5 rounded-full"
                  style={{ background: plan.color, color: "#fff" }}>
                  추천
                </div>
              )}

              <div>
                <div className="flex items-center gap-2 mb-1">
                  <Building2 size={14} style={{ color: plan.color }} />
                  <span className="text-sm font-bold" style={{ color: textPrimary }}>{plan.name}</span>
                </div>
                <div className="flex items-baseline gap-1">
                  <span className="text-2xl font-black" style={{ color: plan.color }}>{plan.price}</span>
                  <span className="text-xs" style={{ color: textMuted }}>{plan.period}</span>
                </div>
              </div>

              <ul className="flex flex-col gap-2 flex-1">
                {plan.features.map((f) => (
                  <li key={f} className="flex items-center gap-2 text-xs" style={{ color: textMuted }}>
                    <Check size={12} style={{ color: plan.color }} className="shrink-0" />
                    {f}
                  </li>
                ))}
              </ul>

              <button
                disabled={isCurrent}
                className="w-full py-2.5 rounded-xl text-sm font-semibold transition-all"
                style={{
                  background: isCurrent ? `${plan.color}20` : plan.color,
                  color: isCurrent ? plan.color : "#fff",
                  cursor: isCurrent ? "default" : "pointer",
                  opacity: isCurrent ? 0.7 : 1,
                }}
              >
                {isCurrent ? "현재 플랜" : plan.id === "free" ? "무료로 시작" : "업그레이드"}
              </button>
            </div>
          );
        })}
      </div>

      {/* 계속하기 */}
      <button
        onClick={onContinue}
        className="text-sm underline transition-colors"
        style={{ color: textMuted }}
      >
        {userPlan === "free" ? "무료 플랜으로 계속하기" : "계속하기"}
      </button>
    </div>
  );
}
