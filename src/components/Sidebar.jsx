/**
 * Sidebar — 좌측 패널
 * - 프로젝트 로고/타이틀
 * - 파일 트리 (프로젝트 구조)
 * - 하단: API 키 입력 + 모델 선택
 */

import React, { useState } from "react";
import useAppStore from "../store/useAppStore";
import {
  FolderTree,
  FolderOpen,
  FileCode,
  ChevronRight,
  ChevronDown,
  Settings,
  Key,
  Cpu,
  Sun,
  Moon,
} from "lucide-react";

export default function Sidebar() {
  const {
    fileTree,
    apiKey,
    setApiKey,
    model,
    setModel,
    availableModels,
    backendHasKey,
    projectFolder,
    selectAndScanFolder,
    isDarkMode,
    toggleDarkMode,
  } = useAppStore();

  const [showSettings, setShowSettings] = useState(false);

  return (
    <div className="h-full flex flex-col bg-transparent border-r border-[var(--border)] text-[15px] transition-colors duration-300">

      {/* ── 스크롤 영역 (프로젝트 트리) ───── */}
      <div className="flex-1 overflow-y-auto">

        {/* ── 파일 트리 ─────────────────────── */}
        <div className="px-2 py-2">
          <div className="flex items-center gap-1.5 px-2 py-1.5 text-[12px] text-slate-400 uppercase tracking-wider">
            <FolderTree size={12} />
            <span className="flex-1 truncate">
              {projectFolder
                ? projectFolder.split(/[/\\]/).pop()
                : "프로젝트"}
            </span>
            <button
              onClick={selectAndScanFolder}
              title="폴더 선택"
              className="p-0.5 hover:text-blue-400 transition-colors rounded"
            >
              <FolderOpen size={12} />
            </button>
          </div>

          {fileTree.length === 0 ? (
            <div className="px-3 py-6 text-center">
              <button
                onClick={selectAndScanFolder}
                className="flex flex-col items-center gap-2 mx-auto text-slate-600 hover:text-slate-400 transition-colors"
              >
                <FolderOpen size={28} />
                <p className="text-[15px]">폴더를 선택하세요</p>
              </button>
            </div>
          ) : (
            <FileTreeNode nodes={fileTree} depth={0} />
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * 파일 트리 노드 (재귀 컴포넌트).
 */
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
  const { openProjectFile, selectedFile, setSelectedFile } = useAppStore();
  const isFolder = node.type === "folder";
  const isSelected = selectedFile?.path === node.path;

  const handleClick = async () => {
    if (isFolder) {
      setExpanded(!expanded);
    } else {
      setSelectedFile(node);
      await openProjectFile(node);
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
