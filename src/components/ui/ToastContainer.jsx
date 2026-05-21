import React from "react";
import useAppStore from "../../store/useAppStore";
import { CheckCircle, AlertCircle, Info, X, ArrowRight } from "lucide-react";

export default function ToastContainer() {
  const { notifications, removeNotification, isDarkMode, switchTeam } = useAppStore();

  const handleAction = (n) => {
    if (n.meta?.action === "switchTeam" && n.meta?.teamId) {
      switchTeam(n.meta.teamId);
      removeNotification(n.id);
    }
  };

  return (
    <div className="fixed bottom-16 right-6 z-[10000] flex flex-col gap-3 pointer-events-none">
      {notifications.map((n) => (
        <Toast
          key={n.id}
          {...n}
          isDarkMode={isDarkMode}
          onClose={() => removeNotification(n.id)}
          onAction={n.meta?.action ? () => handleAction(n) : null}
        />
      ))}
    </div>
  );
}

function Toast({ message, type, onClose, onAction, isDarkMode }) {
  const icons = {
    success: <CheckCircle className="text-emerald-500" size={18} />,
    error: <AlertCircle className="text-red-500" size={18} />,
    info: <Info className="text-blue-500" size={18} />,
    warning: <AlertCircle className="text-amber-500" size={18} />,
  };

  const bgClass = isDarkMode ? "bg-slate-900 border-slate-700" : "bg-white border-slate-200";

  return (
    <div className={`pointer-events-auto flex items-center gap-3 px-4 py-3 rounded-2xl border shadow-2xl animate-fade-in min-w-[280px] max-w-[400px] ${bgClass}`}>
      <div className="shrink-0">{icons[type] || icons.info}</div>
      <div className={`flex-1 text-sm font-medium ${isDarkMode ? "text-slate-200" : "text-slate-700"}`}>
        {message}
      </div>
      {onAction && (
        <button
          onClick={onAction}
          className="shrink-0 flex items-center gap-1 text-xs font-bold text-blue-400 hover:text-blue-300 transition-colors px-2 py-1 rounded-lg hover:bg-blue-500/10"
        >
          이동 <ArrowRight size={12} />
        </button>
      )}
      <button
        onClick={onClose}
        className={`shrink-0 p-1 rounded-lg hover:bg-slate-500/10 transition-colors ${isDarkMode ? "text-slate-500" : "text-slate-400"}`}
      >
        <X size={14} />
      </button>
    </div>
  );
}
