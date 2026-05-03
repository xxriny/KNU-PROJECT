import React from "react";
import { ChevronRight } from "lucide-react";
import { THEME_MAP } from "../../constants/uiConstants";

export default function StudioCard({ id, label, Icon, color, bg, isActive, isDisabled, onClick, isDarkMode }) {
  // 아이콘 색상 추출 및 보정
  let colorName = color.split("-")[1] || "slate";

  // Home(white)이나 특정 예외 처리
  if (id === "home") colorName = "slate";
  else if (id === "memo") colorName = "yellow";
  else if (id === "rtm") colorName = "sky";
  else if (id === "overview") colorName = "indigo";
  else if (id === "sa_overview") colorName = "amber";
  else if (colorName === "white") colorName = "slate";

  const theme = THEME_MAP[colorName] || THEME_MAP.slate;
  const themeColor = isDarkMode ? color : theme.text;

  return (
    <button
      onClick={onClick}
      disabled={isDisabled}
      className={`relative group flex flex-col items-start p-3.5 h-[90px] rounded-2xl border transition-all duration-300 ${isActive
        ? (isDarkMode
          ? "bg-blue-600/15 border-blue-500/50 shadow-[0_0_20px_rgba(56,189,248,0.1)]"
          : `${theme.activeBg} ${theme.border.replace("100", "300")} shadow-sm`)
        : isDisabled
          ? "opacity-10 grayscale cursor-not-allowed border-transparent"
          : isDarkMode
            ? `bg-white/5 border-white/5 hover:bg-white/10`
            : `${theme.bg} ${theme.border} hover:${theme.activeBg} hover:shadow-md`
        }`}
    >
      <div className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 mb-auto transition-transform group-hover:scale-110 ${isDarkMode ? bg : theme.iconBg.replace("500/10", "500/30")
        }`}>
        <Icon size={16} className={themeColor} />
      </div>

      <div className="w-full flex items-center justify-between gap-2 mt-2">
        <span className={`text-[13px] font-bold tracking-tight text-left leading-snug break-keep transition-colors ${isActive
            ? (isDarkMode ? "text-blue-400" : theme.activeText)
            : (isDarkMode ? "text-slate-200 group-hover:text-white" : theme.text)
          }`}>
          {label}
        </span>
        <ChevronRight size={14} className={`shrink-0 transition-transform group-hover:translate-x-1 ${isActive
            ? (isDarkMode ? "text-blue-400" : theme.activeText)
            : (isDarkMode ? "text-slate-600" : theme.text.replace("700", "400"))
          }`} />
      </div>

      {isActive && (
        <div className="absolute inset-0 rounded-2xl border border-blue-500/20 pointer-events-none" />
      )}
    </button>
  );
}
