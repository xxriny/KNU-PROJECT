import React from "react";
import useAppStore from "../../store/useAppStore";
import { Section, EmptyState } from "./SharedComponents";
import { Box, Layers, GitBranch } from "lucide-react";

function SAComponentsTab() {
  const { sa_output } = useAppStore();
  const components = sa_output?.components || sa_output?.data?.components || [];

  if (components.length === 0) {
    return <EmptyState text="설계된 컴포넌트가 없습니다." />;
  }

  const frontend = components.filter(c => c.domain === "Frontend" || c.domain === "F");
  const backend = components.filter(c => c.domain === "Backend" || c.domain === "B");

  const ComponentCard = ({ comp }) => (
    <div className="bg-slate-900/40 border border-slate-700/50 rounded-lg p-4 hover:border-blue-500/50 transition-colors">
      <div className="flex items-center gap-2 mb-2">
        <Box className="text-blue-400" size={16} />
        <h4 className="font-bold text-slate-200">{comp.component_name}</h4>
      </div>
      <p className="text-[13px] text-slate-400 mb-3 leading-relaxed">
        {comp.role}
      </p>
      {comp.dependencies && comp.dependencies.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          <GitBranch size={12} className="text-slate-500 mt-1" />
          {comp.dependencies.map((dep, i) => (
            <span key={i} className="text-[11px] px-1.5 py-0.5 bg-slate-800 text-slate-400 rounded border border-slate-700">
              {dep}
            </span>
          ))}
        </div>
      )}
    </div>
  );

  return (
    <div className="p-4 space-y-6">
      <Section title="Frontend Components" icon={<Layers className="text-fuchsia-400" size={14} />}>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {frontend.map((c, i) => <ComponentCard key={i} comp={c} />)}
        </div>
      </Section>

      <Section title="Backend Components" icon={<Layers className="text-cyan-400" size={14} />}>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {backend.map((c, i) => <ComponentCard key={i} comp={c} />)}
        </div>
      </Section>
    </div>
  );
}

export default SAComponentsTab;
