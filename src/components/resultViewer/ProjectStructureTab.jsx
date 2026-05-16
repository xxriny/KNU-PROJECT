import React, { useState } from "react";
import { useStore } from "../../store/useStore";
import { FolderTree, Folder, FolderOpen, File, ChevronRight, ChevronDown, GitBranch, List } from "lucide-react";
import Card from "../ui/Card";
import Badge from "../ui/Badge";
import ReportLayout, { ReportSection } from "./layout/ReportLayout";

export default function ProjectStructureTab() {
  const { isDarkMode, resultData, sa_output } = useStore(["isDarkMode", "resultData", "sa_output"]);
  const [view, setView] = useState("tree"); // "tree" | "mapping"

  const projectStructure =
    resultData?.sa_project_structure_output ||
    resultData?.sa_project_structure ||
    sa_output?.data?.project_structure ||
    sa_output?.project_structure ||
    null;

  if (!projectStructure) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-slate-500 gap-3">
        <FolderTree size={40} className="opacity-20" />
        <p className="font-bold">프로젝트 구조 데이터가 없습니다.</p>
        <p className="text-sm">SA 분석(UPDATE 또는 CREATE 모드)을 실행하면 생성됩니다.</p>
      </div>
    );
  }

  const { tree, component_mapping = {}, conventions = [] } = projectStructure;
  const componentCount = Object.keys(component_mapping).length;
  const totalFiles = Object.values(component_mapping).reduce((acc, files) => acc + files.length, 0);

  return (
    <ReportLayout
      icon={FolderTree}
      title="Project Structure"
      subtitle="기술 스택과 컴포넌트 설계를 기반으로 생성된 프로젝트 디렉토리 트리와 컴포넌트-파일 매핑입니다."
      badge={`${componentCount} Components · ${totalFiles} Files`}
    >
      {/* 뷰 전환 */}
      <div className={`flex gap-1 p-1 rounded-xl w-fit ${isDarkMode ? "bg-white/5" : "bg-slate-100"}`}>
        {[{ id: "tree", label: "Directory Tree", icon: FolderTree }, { id: "mapping", label: "Component Mapping", icon: GitBranch }].map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setView(id)}
            className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-semibold transition-all ${
              view === id
                ? isDarkMode
                  ? "bg-blue-600 text-white shadow"
                  : "bg-white text-blue-600 shadow"
                : isDarkMode
                ? "text-slate-400 hover:text-white"
                : "text-slate-500 hover:text-slate-800"
            }`}
          >
            <Icon size={14} />
            {label}
          </button>
        ))}
      </div>

      {view === "tree" ? (
        <ReportSection title="Directory Tree" icon={<FolderTree size={20} className="text-teal-400" />}>
          <Card variant="glass" className="p-6 font-mono text-sm overflow-x-auto">
            {tree ? (
              <TreeNode node={tree} depth={0} isDarkMode={isDarkMode} />
            ) : projectStructure?.directories || projectStructure?.files ? (
              <FlatToTree directories={projectStructure.directories || []} files={projectStructure.files || []} isDarkMode={isDarkMode} />
            ) : (
              <p className="text-slate-500 italic">트리 데이터 없음</p>
            )}
          </Card>
        </ReportSection>
      ) : (
        <ReportSection
          title="Component → File Mapping"
          icon={<GitBranch size={20} className="text-blue-400" />}
          badge={componentCount}
        >
          <div className="space-y-4">
            {Object.entries(component_mapping).map(([component, files]) => (
              <MappingCard
                key={component}
                component={component}
                files={files}
                isDarkMode={isDarkMode}
              />
            ))}
            {componentCount === 0 && (
              <p className="text-slate-500 italic p-4">컴포넌트 매핑 없음</p>
            )}
          </div>
        </ReportSection>
      )}

      {/* 네이밍 컨벤션 */}
      {conventions.length > 0 && (
        <ReportSection title="Naming Conventions" icon={<List size={20} className="text-purple-400" />} badge={conventions.length}>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {conventions.map((conv, i) => (
              <div
                key={i}
                className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm ${isDarkMode ? "bg-white/5 text-slate-300" : "bg-slate-50 text-slate-700"}`}
              >
                <span className="text-purple-400 shrink-0">→</span>
                {conv}
              </div>
            ))}
          </div>
        </ReportSection>
      )}
    </ReportLayout>
  );
}

// ── 재귀 트리 컴포넌트 ────────────────────────────────────────

function TreeNode({ node, depth }) {
  const [open, setOpen] = useState(depth < 2);
  const isDir = (node.type_ ?? node.tp ?? node.type) === "dir";
  const name = node.name ?? node.nm ?? "unknown";
  const children = node.children ?? node.ch ?? [];
  const rationale = node.rationale ?? node.rt ?? "";
  const componentId = node.component_id ?? node.ci ?? "";

  const indent = depth * 20;

  return (
    <div>
      <div
        className="flex items-center gap-1.5 py-0.5 hover:bg-white/5 rounded cursor-pointer transition-colors group"
        style={{ paddingLeft: indent + "px" }}
        onClick={() => isDir && setOpen((p) => !p)}
        title={rationale || componentId || undefined}
      >
        {isDir ? (
          <>
            <span className="text-slate-500 w-4 shrink-0">
              {children.length > 0 ? (
                open ? <ChevronDown size={13} /> : <ChevronRight size={13} />
              ) : null}
            </span>
            {open ? (
              <FolderOpen size={14} className="text-yellow-400 shrink-0" />
            ) : (
              <Folder size={14} className="text-yellow-500 shrink-0" />
            )}
          </>
        ) : (
          <>
            <span className="w-4 shrink-0" />
            <File size={13} className="text-blue-400/70 shrink-0" />
          </>
        )}
        <span className={isDir ? "text-yellow-200 font-semibold" : "text-slate-300"}>
          {name}
        </span>
        {componentId && (
          <span className="text-[10px] text-teal-400/60 opacity-0 group-hover:opacity-100 transition-opacity ml-1">
            [{componentId}]
          </span>
        )}
      </div>
      {isDir && open && children.length > 0 && (
        <div>
          {children.map((child, i) => (
            <TreeNode key={i} node={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

// ── 컴포넌트-파일 매핑 카드 ──────────────────────────────────

function MappingCard({ component, files, isDarkMode }) {
  const [expanded, setExpanded] = useState(true);
  return (
    <Card variant="glass" className="overflow-hidden">
      <button
        onClick={() => setExpanded((p) => !p)}
        className={`w-full flex items-center justify-between px-5 py-4 text-left ${
          isDarkMode ? "hover:bg-white/5" : "hover:bg-slate-50"
        } transition-colors`}
      >
        <div className="flex items-center gap-3">
          {expanded ? <ChevronDown size={16} className="text-slate-500" /> : <ChevronRight size={16} className="text-slate-500" />}
          <span className={`font-bold ${isDarkMode ? "text-white" : "text-slate-900"}`}>{component}</span>
        </div>
        <Badge variant="secondary" className="text-[11px]">{files.length} files</Badge>
      </button>
      {expanded && (
        <div className={`px-5 pb-4 space-y-1.5 border-t ${isDarkMode ? "border-white/5" : "border-slate-100"}`}>
          {files.map((file, i) => (
            <div key={i} className="flex items-center gap-2 pt-2">
              <File size={12} className="text-blue-400/60 shrink-0" />
              <span className={`font-mono text-xs ${isDarkMode ? "text-slate-400" : "text-slate-600"}`}>
                {file}
              </span>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

// ── Flat 리스트 -> 트리 변환 컴포넌트 ─────────────────────────────────

function FlatToTree({ directories, files, isDarkMode }) {
  const root = { name: "Project", type: "dir", children: [] };
  
  const ensurePath = (path) => {
    let current = root;
    const parts = path.split('/').filter(Boolean);
    for (const part of parts) {
      let child = current.children.find(c => c.name === part);
      if (!child) {
        child = { name: part, type: "dir", children: [] };
        current.children.push(child);
      }
      current = child;
    }
    return current;
  };

  directories.forEach(d => ensurePath(d));
  files.forEach(f => {
    const parts = f.split('/').filter(Boolean);
    const fileName = parts.pop();
    if (fileName) {
      const parent = ensurePath(parts.join('/'));
      parent.children.push({ name: fileName, type: "file" });
    }
  });

  return (
    <div>
      {root.children.map((child, i) => (
        <TreeNode key={i} node={child} depth={0} isDarkMode={isDarkMode} />
      ))}
    </div>
  );
}
