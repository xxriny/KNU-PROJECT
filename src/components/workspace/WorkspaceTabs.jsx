import React from "react";
import { House, Activity, StickyNote, ChevronDown, Code2, X, LayoutDashboard } from "lucide-react";
import useAppStore from "../../store/useAppStore";

export default function WorkspaceTabs({
  openFiles, activeViewportTab, activateCodeTab, closeFile,
  activeOutputId, activateOutputTab,
  hasProgress, hasSaData,
  pmOpen, setPmOpen, pmRef, PM_TABS, PM_LABELS, isPmActive,
  saOpen, setSaOpen, saRef, SA_TABS, SA_LABELS, isSaActive
}) {
  const userComments = useAppStore(state => state.userComments);
  return (
    <div className="flex flex-col shrink-0">
      {/* Code Tabs Area */}
      <div className="flex items-center border-b border-[var(--border)] min-h-11 px-2">
        <div className="flex items-center gap-0.5 px-1 py-0.5 overflow-x-auto w-full scrollbar-hide">
          {openFiles.length === 0 ? (
            <div className="px-3 py-1.5 text-[14px] text-slate-500 font-medium">열린 코드 탭이 없습니다</div>
          ) : (
            openFiles.map((file) => {
              const isActive = activeViewportTab?.kind === "code" && activeViewportTab.id === file.id;
              return (
                <div
                  key={file.id}
                  className={`group flex items-center gap-2 px-4 py-2 text-[14px] rounded-xl cursor-pointer transition-all ${isActive
                    ? "bg-[var(--accent)]/10 text-[var(--accent)] font-bold shadow-sm"
                    : "text-slate-500 hover:text-slate-300 hover:bg-white/5"
                    }`}
                  onClick={() => activateCodeTab(file.id)}
                >
                  <Code2 size={13} className={isActive ? "text-[var(--accent)]" : "text-slate-500"} />
                  <span className="truncate max-w-[160px]">{file.name}</span>
                  <button
                    onClick={(e) => { e.stopPropagation(); closeFile(file.id); }}
                    className="opacity-0 group-hover:opacity-100 hover:text-red-400 transition-opacity p-0.5"
                  >
                    <X size={11} />
                  </button>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Output Navigation Area */}
      <div className="flex items-center border-b border-[var(--border)] px-4 min-h-12 bg-transparent gap-1">
        <TabButton id="home" activeId={activeOutputId} onClick={() => activateOutputTab("home")} Icon={House} label="Home" />
        
        {hasProgress && (
          <TabButton id="progress" activeId={activeOutputId} onClick={() => activateOutputTab("progress")} Icon={Activity} label="Progress" />
        )}

        <TabButton
          id="overview"
          activeId={activeOutputId}
          onClick={() => activateOutputTab("overview")}
          Icon={LayoutDashboard}
          label="Overview"
        />

        <TabButton 
          id="memo" 
          activeId={activeOutputId} 
          onClick={() => activateOutputTab("memo")} 
          Icon={StickyNote} 
          label="Memo" 
          badge={userComments.length} 
        />
        
        {/* PM Dropdown */}
        <div className="relative h-full flex items-center" ref={pmRef}>
          <DropdownButton
            label="PM"
            isOpen={pmOpen}
            isActive={isPmActive}
            activeLabel={isPmActive ? PM_LABELS[activeOutputId] : null}
            onClick={() => setPmOpen(!pmOpen)}
          />
          {pmOpen && (
            <DropdownMenu tabs={PM_TABS} labels={PM_LABELS} activeId={activeOutputId} onSelect={(id) => { activateOutputTab(id); setPmOpen(false); }} />
          )}
        </div>

        {/* SA Dropdown - Always Visible */}
        <div className="relative h-full flex items-center" ref={saRef}>
          <DropdownButton
            label="SA"
            isOpen={saOpen}
            isActive={isSaActive}
            activeLabel={isSaActive ? SA_LABELS[activeOutputId] : null}
            onClick={() => setSaOpen(!saOpen)}
          />
          {saOpen && (
            <DropdownMenu tabs={SA_TABS} labels={SA_LABELS} activeId={activeOutputId} onSelect={(id) => { activateOutputTab(id); setSaOpen(false); }} />
          )}
        </div>
      </div>
    </div>
  );
}

function TabButton({ id, activeId, onClick, Icon, label, badge }) {
  const isActive = activeId === id;
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-4 py-2 text-[14px] font-bold rounded-xl transition-all ${isActive
        ? "bg-[var(--accent)]/10 text-[var(--accent)] shadow-sm"
        : "text-slate-500 hover:text-slate-300 hover:bg-white/5"
        }`}
    >
      <Icon size={14} />
      <span>{label}</span>
      {badge > 0 && (
        <span className="ml-1 px-1.5 py-0.5 rounded-full bg-blue-500 text-white text-[10px] font-black animate-pulse">
          {badge}
        </span>
      )}
    </button>
  );
}

function DropdownButton({ label, isOpen, isActive, activeLabel, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-4 py-2 text-[14px] font-bold rounded-xl transition-all ${isActive
        ? "bg-[var(--accent)]/10 text-[var(--accent)] shadow-sm"
        : "text-slate-500 hover:text-slate-300 hover:bg-white/5"
        }`}
    >
      <span>{label}</span>
      {activeLabel && <span className="text-[12px] opacity-60 ml-1">› {activeLabel}</span>}
      <ChevronDown size={13} className={`transition-transform duration-300 ${isOpen ? "rotate-180" : ""}`} />
    </button>
  );
}

function DropdownMenu({ tabs, labels, activeId, onSelect }) {
  return (
    <div className="absolute top-full left-0 z-50 glass-panel rounded-xl shadow-2xl overflow-hidden min-w-[200px] border border-white/10">
      <div className="py-2">
        {tabs.map((id) => (
          <button
            key={id}
            onClick={() => onSelect(id)}
            className={`block w-full text-left px-5 py-2.5 text-[14px] font-medium transition-colors ${activeId === id
              ? "bg-[var(--accent)]/20 text-[var(--accent)]"
              : "text-slate-400 hover:bg-white/5 hover:text-white"
              }`}
          >
            {labels[id]}
          </button>
        ))}
      </div>
    </div>
  );
}
