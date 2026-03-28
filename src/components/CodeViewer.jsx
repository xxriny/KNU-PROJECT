/**
 * CodeViewer — Monaco Editor 기반 코드 뷰어
 * 활성 탭의 파일 내용을 렌더링한다.
 */

import React, { useCallback } from "react";
import Editor from "@monaco-editor/react";
import useAppStore from "../store/useAppStore";

export default function CodeViewer() {
  const { openFiles, activeViewportTab, updateOpenFileContent } = useAppStore();

  const handleEditorMount = useCallback((editor) => {
    // 파일 전환/패널 리사이즈 직후 레이아웃이 0으로 잡히는 경우를 방지한다.
    requestAnimationFrame(() => editor.layout());
  }, []);

  const activeFile = activeViewportTab?.kind === "code"
    ? openFiles.find((f) => f.id === activeViewportTab.id)
    : null;

  const handleChange = useCallback((nextValue) => {
    if (!activeFile) return;
    updateOpenFileContent(activeFile.id, nextValue ?? "");
  }, [activeFile, updateOpenFileContent]);

  if (!activeFile) {
    return (
      <div className="h-full flex items-center justify-center text-slate-600 text-sm">
        파일을 선택하세요
      </div>
    );
  }

  return (
    <div className="h-full min-h-0 overflow-hidden">
      <Editor
        key={activeFile.id}
        height="100%"
        path={activeFile.path || activeFile.id}
        language={activeFile.language || "plaintext"}
        value={activeFile.content || ""}
        theme="vs-dark"
        loading={<div className="h-full flex items-center justify-center text-slate-600 text-sm">코드를 불러오는 중...</div>}
        onChange={handleChange}
        onMount={handleEditorMount}
        options={{
          readOnly: false,
          automaticLayout: true,
          minimap: { enabled: false },
          fontSize: 15,
          fontFamily: '"Cascadia Code", "Consolas", "D2Coding", monospace',
          fontWeight: "500",
          lineNumbers: "on",
          scrollBeyondLastLine: false,
          wordWrap: "on",
          padding: { top: 8 },
          renderLineHighlight: "none",
        }}
      />
    </div>
  );
}
