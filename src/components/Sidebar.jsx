import React, { useState } from "react";
import useAppStore from "../store/useAppStore";
import {
  FolderTree,
  FileCode,
  ChevronRight,
  ChevronDown,
} from "lucide-react";

export default function Sidebar() {
  const { fileTree, projectFolder } = useAppStore();

  return (
    <div className="h-full flex flex-col bg-transparent border-r border-[var(--border)] text-[15px] transition-colors duration-300">
      <div className="flex-1 overflow-y-auto">
        <div className="px-2 py-2">
          <div className="flex items-center gap-1.5 px-2 py-1.5 text-[12px] text-slate-400 uppercase tracking-wider">
            <FolderTree size={12} />
            <span className="flex-1 truncate">
              {projectFolder
                ? projectFolder.split(/[/\\]/).pop()
                : "프로젝트"}
            </span>
          </div>

          {fileTree.length === 0 ? (
            <div className="px-3 py-6 text-center">
              <div className="flex flex-col items-center gap-2 mx-auto text-slate-600">
                <p className="text-[15px]">프로젝트 폴더가 없습니다</p>
              </div>
            </div>
          ) : (
            <FileTreeNode nodes={fileTree} depth={0} />
          )}
        </div>
      </div>
    </div>
  );
}

function FileTreeNode({ nodes, depth }) {
  return (
    <div>
      {nodes.map((node) => (
        <FileTreeItem key={node.path || node.name} node={node} depth={depth} />
      ))}
    </div>
  );
}

function FileTreeItem({ node, depth }) {
  const [expanded, setExpanded] = useState(false);
  const { selectedFile, setSelectedFile } = useAppStore();
  const isFolder = node.type === "folder";
  const isSelected = selectedFile?.path === node.path;

  const handleClick = () => {
    if (isFolder) {
      setExpanded(!expanded);
    } else {
      setSelectedFile(node);
    }
  };

  return (
    <div>
      <button
        onClick={handleClick}
        className={`w-full flex items-center gap-1 px-2 py-1 text-[15px] rounded transition-colors ${
          isSelected
            ? "bg-[var(--accent)]/20 text-[var(--accent)] border-r-2 border-[var(--accent)]"
            : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-white/5"
        }`}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
      >
        {isFolder ? (
          expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />
        ) : (
          <FileCode size={12} className="text-slate-500" />
        )}
        <span className="truncate">{node.name}</span>
      </button>

      {isFolder && expanded && node.children && (
        <FileTreeNode nodes={node.children} depth={depth + 1} />
      )}
    </div>
  );
}
