import React from "react";
import useAppStore from "../store/useAppStore";
import { AlertCircle, RefreshCcw, Copy, Bug } from "lucide-react";

export default class GlobalErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    // Zustand store에 에러 로그 기록
    const addDebugLog = useAppStore.getState().addDebugLog;
    if (addDebugLog) {
      addDebugLog({
        level: "critical",
        message: `[RenderCrash] ${error.name}: ${error.message}`,
        rawData: {
          stack: error.stack,
          componentStack: errorInfo.componentStack,
        }
      });
    }
    this.setState({ errorInfo });
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
    // 전역 상태 리셋 유도 (선택 사항)
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      const isDarkMode = useAppStore.getState().isDarkMode;
      
      return (
        <div className={`h-full flex flex-col items-center justify-center p-8 text-center transition-colors duration-200 ${
          isDarkMode ? "bg-slate-900 text-slate-200" : "bg-white text-slate-800"
        }`}>
          <div className="max-w-md w-full">
            <div className={`mb-6 inline-flex p-4 rounded-full ${isDarkMode ? "bg-red-500/10" : "bg-red-50"}`}>
              <AlertCircle size={48} className="text-red-500" />
            </div>
            
            <h1 className="text-2xl font-bold mb-2">Navigator 크래시 감지</h1>
            <p className={`mb-6 text-sm leading-relaxed ${isDarkMode ? "text-slate-400" : "text-slate-500"}`}>
              분석 결과물을 렌더링하는 중 예상치 못한 오류가 발생하여 해당 영역을 격리했습니다. 
              사이드바를 통해 다른 세션을 선택하거나 아래 정보를 저(AI)에게 전달해 주세요.
            </p>

            <div className={`p-4 rounded-lg mb-6 text-left border overflow-hidden ${
              isDarkMode ? "bg-black/30 border-slate-800" : "bg-slate-50 border-slate-200"
            }`}>
              <div className="flex items-center justify-between mb-2">
                <span className="text-[11px] font-mono text-red-500 font-bold uppercase">Technical Details</span>
                <button 
                  onClick={() => {
                    navigator.clipboard.writeText(this.state.error?.stack || "");
                    alert("Stack trace copied!");
                  }}
                  className="p-1 hover:bg-slate-700 rounded transition-colors"
                  title="Copy stack trace"
                >
                  <Copy size={12} />
                </button>
              </div>
              <p className="text-[13px] font-mono text-red-400 mb-1 font-bold break-all">
                {this.state.error?.name}: {this.state.error?.message}
              </p>
              <div className="text-[10px] font-mono text-slate-500 max-h-20 overflow-y-auto">
                {this.state.error?.stack}
              </div>
            </div>

            <div className="flex flex-col gap-3">
              <button
                onClick={this.handleReset}
                className="flex items-center justify-center gap-2 w-full py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-medium transition-all"
              >
                <RefreshCcw size={16} /> 앱 새로고침
              </button>
              
              <div className="flex items-center gap-2 justify-center text-xs text-slate-500">
                <Bug size={14} /> 우측 하단의 디비그 버튼은 계속 사용할 수 있습니다.
              </div>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
