/**
 * CodeViewer — Monaco Editor 기반 코드 뷰어
 * 활성 탭의 파일 내용을 렌더링한다.
 */

import React from "react";
import Editor from "@monaco-editor/react";
import useAppStore from "../store/useAppStore";

export default function CodeViewer() {
  const { openFiles, activeViewportTab } = useAppStore();

  const activeFile = activeViewportTab?.kind === "code"
    ? openFiles.find((f) => f.id === activeViewportTab.id)
    : null;

  if (!activeFile) {
    return (
      <div className="h-full flex items-center justify-center text-slate-600 text-sm">
        파일을 선택하세요
      </div>
    );
  }

  return (
    <div className="h-full">
      <Editor
        height="100%"
        language={activeFile.language || "plaintext"}
        value={activeFile.content || ""}
        theme="vs-dark"
        options={{
          readOnly: true,
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
