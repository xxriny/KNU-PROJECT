import React from "react";
import useAppStore from "../../store/useAppStore";
import { Section, EmptyState } from "./SharedComponents";
import { Globe, ArrowRight, Code } from "lucide-react";

function SAApiTab() {
  const { sa_output, apis: storeApis } = useAppStore();
  const apis = storeApis?.length > 0 ? storeApis : (sa_output?.apis || sa_output?.data?.apis || []);

  if (apis.length === 0) {
    return <EmptyState text="설계된 API가 없습니다." />;
  }

  const SchemaViewer = ({ title, schema }) => (
    <div className="bg-slate-950/40 p-2 rounded border border-slate-800">
      <div className="text-[10px] uppercase tracking-tighter text-slate-500 mb-1">{title}</div>
      <div className="font-mono text-[12px] text-blue-300/90 overflow-x-auto whitespace-pre">
        {schema ? JSON.stringify(schema, null, 2) : "{}"}
      </div>
    </div>
  );

  return (
    <div className="p-4 space-y-6">
      <Section title="API Interface Specifications" icon={<Globe size={14} />}>
        <div className="space-y-4">
          {apis.map((api, idx) => {
            const [method, path] = (api.endpoint || "GET /").split(" ");
            return (
              <div key={idx} className="bg-slate-900/40 border border-slate-700/50 rounded-xl p-5 hover:bg-slate-800/40 transition-all">
                <div className="flex items-center gap-3 mb-4">
                  <span className={`px-3 py-1 rounded text-[11px] font-black uppercase tracking-widest ${
                    method === "GET" ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30" :
                    method === "POST" ? "bg-blue-500/20 text-blue-400 border border-blue-500/30" :
                    "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                  }`}>
                    {method}
                  </span>
                  <code className="text-[15px] font-bold text-slate-100">{path}</code>
                  <p className="ml-auto text-[13px] text-slate-500 italic">{api.description}</p>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-[1fr_auto_1fr] gap-4 items-start">
                  <SchemaViewer title="Request Schema" schema={api.request_schema} />
                  <div className="h-full flex items-center justify-center pt-6 opacity-30">
                    <ArrowRight size={20} className="text-slate-500" />
                  </div>
                  <SchemaViewer title="Response Schema" schema={api.response_schema} />
                </div>
              </div>
            );
          })}
        </div>
      </Section>
    </div>
  );
}

export default SAApiTab;
