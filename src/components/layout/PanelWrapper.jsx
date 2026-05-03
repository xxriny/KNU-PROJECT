import React from "react";
import { Library, X } from "lucide-react";
import useAppStore from "../../store/useAppStore";

export default function PanelWrapper({ title, onClose, children }) {
  const { isDarkMode } = useAppStore();
  return (
    <div className="h-full flex flex-col min-h-0">
      <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--border)] shrink-0 bg-[rgba(255,255,255,0.02)]">
        <div className="flex items-center gap-2">
          <Library size={14} className="text-blue-400" />
          <span className="text-sm font-medium text-[var(--text-secondary)]">{title}</span>
        </div>
        <button
          onClick={onClose}
          className="p-1.5 rounded-md text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-white/10 transition-colors"
        >
          <X size={14} />
        </button>
      </div>
      <div className="flex-1 min-h-0 overflow-auto">
        {children}
      </div>
    </div>
  );
}
