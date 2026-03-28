import React from "react";
import useAppStore from "../store/useAppStore";
import { Clock3, X as XIcon } from "lucide-react";

export default function SessionPanel() {
  const { sessions, currentSessionId, loadSession, deleteSession } = useAppStore();

  return (
    <div className="h-full min-h-0 flex flex-col bg-slate-900 text-sm overflow-hidden">
      <div className="flex items-center gap-2 px-3 py-3 border-b border-slate-700/50">
        <Clock3 size={14} className="text-blue-400" />
        <span className="text-sm font-medium text-slate-300">세션</span>
        <span className="ml-auto text-[12px] text-slate-500">{sessions.length}</span>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto p-2 space-y-1">
        {sessions.length === 0 ? (
          <div className="px-2 py-4 text-center text-sm text-slate-600">
            세션이 없습니다
          </div>
        ) : (
          sessions.map((session) => {
            const isActive = currentSessionId === session.id;
            return (
              <div
                key={session.id}
                onClick={() => loadSession(session.id)}
                className={`group rounded-md px-2 py-2 cursor-pointer transition-colors ${
                  isActive
                    ? "bg-blue-600/15 text-blue-300"
                    : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"
                }`}
              >
                <div className="flex items-start gap-2">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm truncate">{session.projectName || session.name}</p>
                    <p className="mt-1 text-[12px] text-slate-600 truncate">
                      {new Date(session.createdAt).toLocaleString("ko", {
                        month: "2-digit",
                        day: "2-digit",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </p>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteSession(session.id);
                    }}
                    className="opacity-0 group-hover:opacity-100 p-0.5 hover:text-red-400 transition-opacity"
                    title="세션 삭제"
                  >
                    <XIcon size={11} />
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
