import React, { useState, useEffect, useRef } from "react";
import useAppStore from "../store/useAppStore";
import { Sparkles, Layers, ScanSearch, Send, Paperclip, X, GitBranch, Loader2, Search } from "lucide-react";

const MODES = [
  {
    key: "create",
    label: "신규 기획",
    desc: "아이디어를 구조화된 요구사항으로 변환",
    icon: Sparkles,
    color: "from-blue-500 to-cyan-500",
    shadowColor: "rgba(59, 130, 246, 0.4)",
  },
  {
    key: "update",
    label: "기능 확장",
    desc: "기존 프로젝트에 새 기능 요구사항 추가",
    icon: Layers,
    color: "from-emerald-500 to-teal-500",
    shadowColor: "rgba(16, 185, 129, 0.4)",
  },
  {
    key: "reverse",
    label: "재분석",
    desc: "기존 시스템에서 RTM을 역추출",
    icon: ScanSearch,
    color: "from-purple-500 to-pink-500",
    shadowColor: "rgba(168, 85, 247, 0.4)",
  },
];



export default function HomeScreen() {
  const {
    startAnalysis,
    activateOutputTab,
    apiKey,
    model,
    selectedMode,
    setSelectedMode,
    projectFolder,
    setProjectFolder,
    isDarkMode,
    authToken,
    backendPort,
    githubToken,
    githubOwner,
    githubRepo,
    setGithubSettings,
  } = useAppStore();

  const [inputText, setInputText] = useState("");
  const [contextText, setContextText] = useState("");
  const [showContext, setShowContext] = useState(false);
  const [projectTitle, setProjectTitle] = useState("새 프로젝트");
  const textareaRef = useRef(null);

  const [repoList, setRepoList] = useState([]);
  const [repoLoading, setRepoLoading] = useState(false);
  const [repoSearch, setRepoSearch] = useState("");
  const [showRepoPicker, setShowRepoPicker] = useState(false);
  const [repoScopeError, setRepoScopeError] = useState(false);
  const [selectedRepo, setSelectedRepo] = useState(null);

  // 전역 스토어의 레포 정보와 동기화
  useEffect(() => {
    if (githubOwner && githubRepo) {
      setSelectedRepo({ full_name: `${githubOwner}/${githubRepo}`, owner: githubOwner, name: githubRepo });
      if (projectFolder !== `${githubOwner}/${githubRepo}`) {
        setProjectFolder(`${githubOwner}/${githubRepo}`);
      }
    }
  }, [githubOwner, githubRepo, projectFolder, setProjectFolder]);

  const loadRepos = async () => {
    if (!authToken) return;
    setRepoLoading(true);
    setRepoScopeError(false);
    try {
      const port = backendPort || 8000;
      const res = await fetch(`http://127.0.0.1:${port}/auth/github/repos`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      const data = await res.json();
      if (data.status === "ok") {
        setRepoList(data.repos);
        setShowRepoPicker(true);
      } else {
        setRepoScopeError(true);
      }
    } catch (_) {
      setRepoScopeError(true);
    } finally {
      setRepoLoading(false);
    }
  };

  const selectRepo = async (repo) => {
    setSelectedRepo(repo);
    setProjectFolder(repo.full_name);
    // 전역 스토어 동기화
    setGithubSettings(githubToken, repo.owner, repo.name);
    setShowRepoPicker(false);
    setRepoSearch("");

    // 팀 기본 레포지토리로 백엔드에도 즉시 반영 (동기화 요구사항)
    try {
      const port = backendPort || 8000;
      await fetch(`http://127.0.0.1:${port}/api/teams/me/github`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${authToken}` },
        body: JSON.stringify({ github_repo: repo.full_name }),
      });
    } catch (_) {}
  };

  const isReverseMode = selectedMode === "reverse";
  const trimmedInput = inputText.trim();
  const canSubmit = isReverseMode ? Boolean(projectFolder) : Boolean(trimmedInput);

  const handleSubmit = () => {
    if (!canSubmit) return;
    activateOutputTab("progress");
    startAnalysis(trimmedInput, contextText.trim(), apiKey, model, selectedMode, projectTitle);
    setInputText("");
    setContextText("");
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (canSubmit) handleSubmit();
    }
  };

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 150) + 'px';
    }
  }, [inputText]);

  return (
    <div
      className={`h-full w-full flex flex-col items-center relative overflow-hidden ${isDarkMode ? "bg-transparent text-slate-200" : "bg-transparent text-slate-800"
        }`}
    >
      {/* ── 배경 장식 (Subdued) ─────────────────── */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div
          className="absolute -top-[10%] -left-[5%] w-[50%] h-[50%] bg-blue-500/10 blur-[120px] rounded-full"
        />
      </div>

      <div className="w-full max-w-5xl flex flex-col items-center flex-1 relative z-10 px-8 h-full">
        {/* ── 상단/중앙 콘텐츠 (타이틀 및 카드) ────────────────── */}
        <div className="flex-1 flex flex-col items-center justify-center w-full min-h-0 py-10">
          <div
            className="text-center mb-16 shrink-0"
          >
            <h1 className="text-5xl font-black mb-3 tracking-widest drop-shadow-sm">
              <span className="text-gradient">NAVIGATOR</span>
            </h1>
            <p className={`text-[17px] font-medium opacity-50 ${isDarkMode ? "text-slate-400" : "text-slate-600"}`}>
              아이디어를 구조화된 요구사항 명세서로 변환합니다
            </p>
          </div>

          {/* ── 모드 선택 (Grid) ───────────────── */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 lg:gap-6 w-full max-w-4xl px-6">
            {MODES.map((mode, idx) => (
              <div
                key={mode.key}
                onClick={() => {
                  setSelectedMode(mode.key);
                  if (mode.key === "reverse" && !projectFolder) {
                    setShowContext(true);
                  }
                }}
                className={`group flex flex-row lg:flex-col items-center text-left lg:text-center p-4 lg:p-6 rounded-2xl lg:rounded-3xl border cursor-pointer transition-all duration-300 relative overflow-hidden ${selectedMode === mode.key
                  ? "glass-card border-[var(--accent)] shadow-2xl scale-[1.01] lg:scale-[1.05] bg-[var(--accent)]/5"
                  : `glass-card border-white/5 hover:border-white/10 ${isDarkMode ? "bg-white/5" : "bg-slate-50 border-slate-100"}`
                  }`}
              >
                <div className={`w-10 h-10 lg:w-14 lg:h-14 rounded-xl lg:rounded-2xl bg-gradient-to-br ${mode.color} flex items-center justify-center mb-0 lg:mb-4 mr-4 lg:mr-0 shadow-lg group-hover:scale-110 transition-transform shrink-0`}>
                  <mode.icon className="text-white w-5 h-5 lg:w-7 lg:h-7" />
                </div>
                <div className="flex flex-col">
                  <h3 className="text-sm lg:text-lg font-bold mb-0.5 lg:mb-2">
                    {mode.label}
                  </h3>
                  <p className={`text-[10px] lg:text-[13px] leading-relaxed opacity-50 line-clamp-2`}>
                    {mode.desc}
                  </p>
                </div>

                {selectedMode === mode.key && (
                  <div
                    className="absolute inset-0 border-2 border-[var(--accent)]/40 rounded-2xl lg:rounded-3xl pointer-events-none"
                  />
                )}
              </div>
            ))}
          </div>
        </div>

        {/* ── 입력 영역 (Bottom Docked - Absolute 모드로 변경하여 레이아웃 고정) ─────────────────────── */}
        <div className="absolute bottom-12 w-full max-w-4xl px-8 z-50">
          <div
            className="flex flex-col gap-4"
          >

            <div className={`w-full relative rounded-full p-2 px-6 shadow-2xl flex items-center border border-white/5 ${isDarkMode ? "bg-[#161b22]/90 backdrop-blur-2xl" : "bg-white/90 backdrop-blur-xl border-slate-200"
              }`}>
              <div className="flex-1">
                <textarea
                  ref={textareaRef}
                  value={inputText}
                  onChange={(e) => setInputText(e.target.value)}
                  onKeyDown={handleKeyDown}
                  rows={1}
                  placeholder="아이디어를 입력하세요..."
                  className="w-full bg-transparent border-none focus:outline-none focus:ring-0 text-[16px] py-3 resize-none scrollbar-hide placeholder:text-slate-500"
                />
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={() => setShowContext(!showContext)}
                  className={`p-2 rounded-full transition-all ${showContext ? "bg-[var(--accent)] text-white shadow-lg" : "text-slate-500 hover:bg-white/10"
                    }`}
                  title="컨텍스트 추가"
                >
                  <Paperclip size={20} />
                </button>
                <button
                  onClick={handleSubmit}
                  disabled={!selectedMode || !canSubmit}
                  className={`w-11 h-11 flex items-center justify-center rounded-full transition-all ${canSubmit
                    ? "bg-blue-600 text-white hover:bg-blue-500 shadow-lg"
                    : "bg-white/5 text-slate-700 cursor-not-allowed"
                    }`}
                >
                  <Send size={20} />
                </button>
              </div>
            </div>

            <footer className="w-full px-6 flex items-center justify-between text-[11px] font-medium text-slate-600/50 uppercase tracking-widest opacity-60">
              <div className="flex items-center gap-4">
                <span>NAVIGATOR PM PIPELINE</span>
                <div className="w-1 h-1 rounded-full bg-slate-800" />
                <span>STABLE RELEASE</span>
              </div>
              <span>PROMPT + ENTER TO PROCESS</span>
            </footer>
          </div>
        </div>
      </div>

      {/* ── 프로젝트 설정 모달 (showContext) ── */}
      {showContext && (
        <div className="absolute inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-8">
          <div className="w-[600px] bg-[#1e1e24] border border-white/10 rounded-2xl shadow-2xl flex flex-col overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-white/5">
              <h2 className="text-[15px] font-bold text-slate-200">"{projectTitle}"의 환경 설정</h2>
              <button onClick={() => setShowContext(false)} className="p-1.5 hover:bg-white/10 rounded-full transition-colors text-slate-400">
                <X size={16} />
              </button>
            </div>

            {/* Body */}
            <div className="p-6 flex flex-col gap-6">
              {/* Repo Picker */}
              <div className="bg-[#131317] border border-white/5 rounded-xl flex flex-col overflow-hidden">
                {/* Selected repo display + button */}
                <div className="flex items-center gap-3 px-4 py-3 border-b border-white/5">
                  <div className="flex-1 min-w-0">
                    {selectedRepo ? (
                      <div className="flex items-center gap-2">
                        <GitBranch size={15} className="text-slate-400 shrink-0" />
                        <span className="text-sm font-semibold text-slate-200 truncate">{selectedRepo.full_name}</span>
                        {selectedRepo.private && <span className="text-[10px] text-amber-400 border border-amber-400/30 px-1.5 py-0.5 rounded shrink-0">private</span>}
                        {selectedRepo.language && <span className="text-[11px] text-slate-500 shrink-0">{selectedRepo.language}</span>}
                      </div>
                    ) : (
                      <span className="text-sm text-slate-500 opacity-60">선택된 레포지토리 없음</span>
                    )}
                  </div>
                  <button
                    onClick={loadRepos}
                    disabled={repoLoading || !authToken}
                    className="flex items-center gap-2 px-3 py-1.5 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg text-sm font-medium transition-colors disabled:opacity-40"
                  >
                    {repoLoading ? <Loader2 size={14} className="animate-spin" /> : <GitBranch size={14} />}
                    <span>레포 선택</span>
                  </button>
                </div>

                {repoScopeError && (
                  <p className="text-xs text-amber-400 px-4 py-2 border-b border-white/5">
                    GitHub 재연결이 필요합니다. 설정에서 연결 해제 후 다시 연결하세요.
                  </p>
                )}

                {!authToken && (
                  <p className="text-xs text-slate-500 px-4 py-2 border-b border-white/5">
                    GitHub에 로그인하면 레포지토리를 선택할 수 있습니다.
                  </p>
                )}

                {/* Inline picker */}
                {showRepoPicker && repoList.length > 0 && (
                  <div className="flex flex-col">
                    <div className="px-3 py-2 border-b border-white/5">
                      <div className="flex items-center gap-2 bg-white/5 rounded-lg px-3 py-1.5">
                        <Search size={13} className="text-slate-500 shrink-0" />
                        <input
                          autoFocus
                          value={repoSearch}
                          onChange={(e) => setRepoSearch(e.target.value)}
                          placeholder="레포 검색..."
                          className="flex-1 bg-transparent text-sm focus:outline-none placeholder:text-slate-600"
                        />
                      </div>
                    </div>
                    <ul className="max-h-48 overflow-y-auto divide-y divide-white/5">
                      {repoList
                        .filter(r => r.full_name.toLowerCase().includes(repoSearch.toLowerCase()))
                        .map(repo => (
                          <li
                            key={repo.full_name}
                            onClick={() => selectRepo(repo)}
                            className="flex items-center gap-2 px-4 py-2.5 hover:bg-white/5 cursor-pointer transition-colors"
                          >
                            <GitBranch size={13} className="text-slate-500 shrink-0" />
                            <span className="text-sm font-medium text-slate-200 truncate flex-1">{repo.name}</span>
                            <span className="text-xs text-slate-500 shrink-0">{repo.owner}</span>
                            {repo.private && <span className="text-[10px] text-amber-400 shrink-0">private</span>}
                            {repo.language && <span className="text-[10px] text-slate-600 shrink-0">{repo.language}</span>}
                          </li>
                        ))}
                    </ul>
                  </div>
                )}

                {!showRepoPicker && selectedRepo?.description && (
                  <p className="text-xs text-slate-500 px-4 py-2">{selectedRepo.description}</p>
                )}
              </div>

              {/* Title Input */}
              <div className="flex flex-col gap-2">
                <label className="text-xs text-slate-400 font-medium px-1">프로젝트 제목</label>
                <input
                  type="text"
                  value={projectTitle}
                  onChange={(e) => setProjectTitle(e.target.value)}
                  className="w-full bg-[#131317] border border-white/10 rounded-lg px-4 py-3 text-sm focus:outline-none focus:border-[var(--accent)] transition-colors"
                  placeholder="제목을 입력하세요"
                />
              </div>
            </div>

            {/* Footer */}
            <div className="px-6 py-4 border-t border-white/5 flex justify-end">
              <button
                onClick={() => setShowContext(false)}
                className="px-6 py-2 bg-white/10 hover:bg-white/20 text-white rounded-lg text-sm font-bold transition-colors"
              >
                완료
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
