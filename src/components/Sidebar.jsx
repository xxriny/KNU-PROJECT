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
  } = useAppStore();

  const [showSettings, setShowSettings] = useState(false);

  return (
    <div className="h-full flex flex-col bg-slate-900 border-r border-slate-700/50 text-[15px]">
      {/* ── 헤더 ──────────────────────────── */}
      <div className="px-4 py-3 border-b border-slate-700/50">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-blue-600 flex items-center justify-center">
            <Cpu size={14} className="text-white" />
          </div>
          <div>
            <h1 className="text-base font-semibold text-slate-200">PM Agent</h1>
            <p className="text-[12px] text-slate-500">Pipeline v2.0</p>
          </div>
        </div>
      </div>

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
      {/* ── 설정 영역 ─────────────────────── */}
      <div className="border-t border-slate-700/50">
        <button
          onClick={() => setShowSettings(!showSettings)}
          className="w-full flex items-center gap-2 px-4 py-2.5 text-[15px] text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 transition-colors"
        >
          <Settings size={13} />
          <span>설정</span>
          <ChevronRight
            size={12}
            className={`ml-auto transition-transform ${showSettings ? "rotate-90" : ""}`}
          />
        </button>

        {showSettings && (
          <div className="px-3 pb-3 space-y-2">
            {/* API Key */}
            <div>
              <label className="flex items-center gap-1 text-[12px] text-slate-500 mb-1">
                <Key size={10} />
                Gemini API Key
                {backendHasKey && !apiKey && (
                  <span className="ml-auto text-[12px] text-green-500 font-medium">.env 사용 중</span>
                )}
              </label>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={backendHasKey ? ".env에서 자동 로드됨" : "API 키 입력..."}
                className={`w-full px-2.5 py-1.5 text-[15px] bg-slate-800 border rounded-md text-slate-300 placeholder-slate-600 focus:outline-none focus:border-blue-500 transition-colors ${
                  backendHasKey && !apiKey
                    ? "border-green-700/50"
                    : "border-slate-700"
                }`}
              />
              {backendHasKey && !apiKey && (
                <p className="text-[12px] text-slate-500 mt-1">
                  직접 입력 시 .env보다 우선 적용
                </p>
              )}
            </div>

            {/* Model */}
            <div>
              <label className="flex items-center gap-1 text-[12px] text-slate-500 mb-1">
                <Cpu size={10} />
                모델
              </label>
              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="w-full px-2.5 py-1.5 text-[15px] bg-slate-800 border border-slate-700 rounded-md text-slate-300 focus:outline-none focus:border-blue-500 transition-colors"
              >
                {availableModels.map((availableModel) => (
                  <option key={availableModel} value={availableModel}>
                    {availableModel}
                  </option>
                ))}
              </select>
            </div>
          </div>
        )}
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
            ? "bg-blue-600/20 text-blue-300"
            : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
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
