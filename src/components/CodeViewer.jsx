import React from "react";
import Editor from "@monaco-editor/react";
import useCodeEditor from "../hooks/useCodeEditor";

/**
 * CodeViewer — Monaco Editor 기반 코드 뷰어
 */
export default function CodeViewer() {
  const {
    activeFile,
    isDarkMode,
    handleEditorBeforeMount,
    handleEditorMount,
    handleChange
  } = useCodeEditor();

  if (!activeFile) {
    return (
      <div className="h-full flex items-center justify-center text-slate-500 text-[14px] font-medium animate-fade-in">
        파일을 선택하여 편집을 시작하세요
      </div>
    );
  }

  return (
    <div className="h-full min-h-0 overflow-hidden animate-fade-in">
      <Editor
        key={activeFile.id}
        height="100%"
        path={activeFile.path || activeFile.id}
        language={activeFile.language || "plaintext"}
        value={activeFile.content || ""}
        theme={isDarkMode ? "navigator-dark" : "navigator-light"}
        loading={<div className="h-full flex items-center justify-center text-slate-500 text-sm">Initializing Editor...</div>}
        onChange={handleChange}
        beforeMount={handleEditorBeforeMount}
        onMount={handleEditorMount}
        options={{
          readOnly: false,
          automaticLayout: true,
          minimap: { enabled: false },
          fontSize: 14,
          fontFamily: '"Cascadia Code", "Consolas", "D2Coding", monospace',
          fontWeight: "500",
          lineNumbers: "on",
          scrollBeyondLastLine: false,
          wordWrap: "on",
          padding: { top: 12 },
          renderLineHighlight: "none",
          smoothScrolling: true,
          cursorSmoothCaretAnimation: "on",
          cursorBlinking: "smooth",
        }}
      />
    </div>
  );
}
