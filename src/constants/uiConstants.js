import {
  House, Activity, Table2, Layers, Globe, Database, StickyNote, FileText,
} from "lucide-react";

export const ICON_PANELS = [
  { id: "home", label: "Home", Icon: House, group: null, color: "text-white", bg: "bg-slate-500/10" },
  { id: "progress", label: "Progress", Icon: Activity, group: null, color: "text-yellow-400", bg: "bg-yellow-500/10" },
  { id: "memo", label: "Memos", Icon: StickyNote, group: null, color: "text-amber-300", bg: "bg-amber-500/10" },
  { id: "rtm", label: "RTM", Icon: Table2, group: "pm", color: "text-cyan-400", bg: "bg-cyan-500/10" },
  { id: "stack", label: "Stack", Icon: Layers, group: "pm", color: "text-indigo-400", bg: "bg-indigo-500/10" },
  { id: "sa_components", label: "Components", Icon: Layers, group: "sa", color: "text-teal-400", bg: "bg-teal-500/10" },
  { id: "sa_api", label: "API Spec", Icon: Globe, group: "sa", color: "text-blue-400", bg: "bg-blue-500/10" },
  { id: "sa_db", label: "Database", Icon: Database, group: "sa", color: "text-rose-400", bg: "bg-rose-500/10" },
];

export const THEME_MAP = {
  slate: { bg: "bg-slate-50/50", activeBg: "bg-slate-100", text: "text-slate-700", activeText: "text-slate-900", border: "border-slate-100", iconBg: "bg-slate-500/10" },
  blue: { bg: "bg-blue-50/50", activeBg: "bg-blue-100/60", text: "text-blue-700", activeText: "text-blue-800", border: "border-blue-100", iconBg: "bg-blue-500/10" },
  sky: { bg: "bg-sky-50/50", activeBg: "bg-sky-100/60", text: "text-sky-600", activeText: "text-sky-800", border: "border-sky-100", iconBg: "bg-sky-500/10" },
  yellow: { bg: "bg-yellow-50/50", activeBg: "bg-yellow-100/60", text: "text-yellow-700", activeText: "text-yellow-800", border: "border-yellow-100", iconBg: "bg-yellow-500/10" },
  cyan: { bg: "bg-cyan-50/50", activeBg: "bg-cyan-100/60", text: "text-cyan-700", activeText: "text-cyan-800", border: "border-cyan-100", iconBg: "bg-cyan-500/10" },
  green: { bg: "bg-green-50/50", activeBg: "bg-green-100/60", text: "text-green-700", activeText: "text-green-800", border: "border-green-100", iconBg: "bg-green-500/10" },
  amber: { bg: "bg-amber-50/50", activeBg: "bg-amber-100/60", text: "text-amber-700", activeText: "text-amber-800", border: "border-amber-100", iconBg: "bg-amber-500/10" },
  indigo: { bg: "bg-indigo-50/50", activeBg: "bg-indigo-100/60", text: "text-indigo-700", activeText: "text-indigo-800", border: "border-indigo-100", iconBg: "bg-indigo-500/10" },
  teal: { bg: "bg-teal-50/50", activeBg: "bg-teal-100/60", text: "text-teal-700", activeText: "text-teal-800", border: "border-teal-100", iconBg: "bg-teal-500/10" },
  rose: { bg: "bg-rose-50/50", activeBg: "bg-rose-100/60", text: "text-rose-700", activeText: "text-rose-800", border: "border-rose-100", iconBg: "bg-rose-500/10" },
};
