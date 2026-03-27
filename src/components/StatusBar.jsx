/**
 * StatusBar — 하단 상태 바
 * WebSocket 연결 상태 + 파이프라인 상태 + 모델 정보
 */

import React from "react";
import useAppStore from "../store/useAppStore";
import { Wifi, WifiOff, Loader2, Cpu } from "lucide-react";

export default function StatusBar() {
  const { wsStatus, pipelineStatus, model, backendPort } = useAppStore();

  const wsColors = {
    connected: "text-green-400",
    connecting: "text-yellow-400",
    disconnected: "text-red-400",
    error: "text-red-400",
  };

  const wsLabels = {
    connected: "연결됨",
    connecting: "연결 중...",
    disconnected: "연결 끊김",
    error: "연결 오류",
  };

  const pipelineLabels = {
    idle: "대기",
    running: "분석 중...",
    done: "완료",
    error: "오류",
  };

  return (
    <div className="h-6 flex items-center justify-between px-3 bg-slate-900 border-t border-slate-700/50 text-[12px] text-slate-500">
      {/* 좌측 */}
      <div className="flex items-center gap-4">
        {/* WebSocket 상태 */}
        <div className="flex items-center gap-1">
          {wsStatus === "connected" ? (
            <Wifi size={10} className={wsColors[wsStatus]} />
          ) : wsStatus === "connecting" ? (
            <Loader2 size={10} className="text-yellow-400 animate-spin" />
          ) : (
            <WifiOff size={10} className={wsColors[wsStatus]} />
          )}
          <span className={wsColors[wsStatus]}>{wsLabels[wsStatus]}</span>
          {backendPort && (
            <span className="text-slate-600">:{backendPort}</span>
          )}
        </div>

        {/* 파이프라인 상태 */}
        <div className="flex items-center gap-1">
          {pipelineStatus === "running" && (
            <Loader2 size={10} className="text-blue-400 animate-spin" />
          )}
          <span>{pipelineLabels[pipelineStatus]}</span>
        </div>
      </div>

      {/* 우측 */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1">
          <Cpu size={10} />
          <span>{model}</span>
        </div>
        <span>PM Agent Pipeline v2.0</span>
      </div>
    </div>
  );
}
