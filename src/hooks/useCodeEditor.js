import { useCallback } from "react";
import useAppStore from "../store/useAppStore";

export default function useCodeEditor() {
  const isDarkMode = useAppStore((state) => state.isDarkMode);
  const openFiles = useAppStore((state) => state.openFiles);
  const activeViewportTab = useAppStore((state) => state.activeViewportTab);
  const updateOpenFileContent = useAppStore((state) => state.updateOpenFileContent);

  const activeFile = activeViewportTab?.kind === "code"
    ? openFiles.find((f) => f.id === activeViewportTab.id)
    : null;

  const handleEditorBeforeMount = useCallback((monaco) => {
    monaco.editor.defineTheme("navigator-dark", {
      base: "vs-dark",
      inherit: true,
      rules: [],
      colors: {
        "editor.background": "#13171F",
        "editor.lineHighlightBackground": "#ffffff0a",
        "editorCursor.foreground": "#38bdf8",
        "editorIndentGuide.activeBackground": "#38bdf855",
      },
    });

    monaco.editor.defineTheme("navigator-light", {
      base: "vs",
      inherit: true,
      rules: [],
      colors: {
        "editor.background": "#f8fafc",
        "editor.lineHighlightBackground": "#00000005",
      },
    });
  }, []);

  const handleEditorMount = useCallback((editor) => {
    requestAnimationFrame(() => editor.layout());
  }, []);

  const handleChange = useCallback((nextValue) => {
    if (!activeFile) return;
    updateOpenFileContent(activeFile.id, nextValue ?? "");
  }, [activeFile, updateOpenFileContent]);

  return {
    activeFile,
    isDarkMode,
    handleEditorBeforeMount,
    handleEditorMount,
    handleChange
  };
}
