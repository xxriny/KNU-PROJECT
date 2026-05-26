import React, { useState, useEffect } from "react";
import useAppStore from "../../store/useAppStore";
import { serverRequest } from "../../api/serverClient";
import {
  Sparkles, Layers, ScanSearch, GitBranch, Search,
  Loader2, ArrowLeft, X,
} from "lucide-react";

const MODES = [
  {
    key: "create",
    label: "신규 기획",
    sub: "Zero to One",
    desc: "백지 상태에서 AI와 대화하며 RTM·API·DB를 만들고, 완성 후 빈 GitHub 레포에 내보냅니다.",
    icon: Sparkles,
    color: "from-blue-500 to-cyan-500",
  },
  {
    key: "update",
    label: "기능 확장",
    sub: "One to N",
    desc: "기존 GitHub 레포의 코드와 기획서를 동기화하며 새 기능을 더합니다.",
    icon: Layers,
    color: "from-emerald-500 to-teal-500",
  },
  {
    key: "reverse",
    label: "재분석",
    sub: "Legacy to Agile",
    desc: "문서 없이 코드만 있는 레거시 프로젝트를 AI가 뜯어보고 최신 기획서(RTM)로 역산출합니다.",
    icon: ScanSearch,
    color: "from-purple-500 to-pink-500",
  },
];

/**
 * 로그인 직후 / 새 프로젝트 시작 직후 등장하는 온보딩 브릿지.
 * Step 1: 모드 선택 (CREATE / UPDATE / REVERSE)
 * Step 2: UPDATE / REVERSE만 — GitHub 레포 & 브랜치 선택
 * CREATE 선택 시 Step 2를 건너뛰고 즉시 dismiss → HomeScreen 빈 프롬프트로 진입.
 */
export default function ModeBridge() {
  const isDarkMode = useAppStore((s) => s.isDarkMode);
  const setSelectedMode = useAppStore((s) => s.setSelectedMode);
  const setShowOnboardingBridge = useAppStore((s) => s.setShowOnboardingBridge);
  const githubToken = useAppStore((s) => s.githubToken);
  const githubOwner = useAppStore((s) => s.githubOwner);
  const githubRepo = useAppStore((s) => s.githubRepo);
  const githubBranch = useAppStore((s) => s.githubBranch);
  const setGithubSettings = useAppStore((s) => s.setGithubSettings);
  const setGithubBranch = useAppStore((s) => s.setGithubBranch);
  const setProjectFolder = useAppStore((s) => s.setProjectFolder);
  const authToken = useAppStore((s) => s.authToken);
  const currentUser = useAppStore((s) => s.currentUser);

  const [step, setStep] = useState(1);
  const [pickedMode, setPickedMode] = useState(null);

  const [repoList, setRepoList] = useState([]);
  const [repoLoading, setRepoLoading] = useState(false);
  const [repoSearch, setRepoSearch] = useState("");
  const [repoScopeError, setRepoScopeError] = useState(false);
  const [selectedRepo, setSelectedRepo] = useState(() =>
    githubOwner && githubRepo
      ? { full_name: `${githubOwner}/${githubRepo}`, owner: githubOwner, name: githubRepo }
      : null
  );
  const [branchList, setBranchList] = useState([]);
  const [branchLoading, setBranchLoading] = useState(false);

  const dismiss = () => setShowOnboardingBridge(false);

  const pickMode = (mode) => {
    setPickedMode(mode);
    setSelectedMode(mode);
    if (mode === "create") {
      dismiss();
    } else {
      setStep(2);
      if (selectedRepo) loadBranches(selectedRepo.owner, selectedRepo.name);
    }
  };

  const loadRepos = async () => {
    if (!authToken) return;
    setRepoLoading(true);
    setRepoScopeError(false);
    try {
      const data = await serverRequest("/auth/github/repos", {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (data.status === "ok") {
        setRepoList(data.repos);
      } else {
        setRepoScopeError(true);
      }
    } catch {
      setRepoScopeError(true);
    } finally {
      setRepoLoading(false);
    }
  };

  const loadBranches = async (owner, repo) => {
    setBranchLoading(true);
    try {
      const data = await serverRequest(
        `/auth/github/branches?owner=${encodeURIComponent(owner)}&repo=${encodeURIComponent(repo)}`,
        { headers: { Authorization: `Bearer ${authToken}` } },
      );
      setBranchList(data.data || []);
    } catch {
      setBranchList([]);
    } finally {
      setBranchLoading(false);
    }
  };

  const selectRepo = async (repo) => {
    setSelectedRepo(repo);
    setProjectFolder(repo.full_name);
    setBranchList([]);
    setGithubSettings(githubToken, repo.owner, repo.name);
    loadBranches(repo.owner, repo.name);
    if (currentUser?.team_id) {
      try {
        await serverRequest(`/auth/teams/${currentUser.team_id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${authToken}` },
          body: JSON.stringify({ github_repo: repo.full_name }),
        });
      } catch { /* ignore */ }
    }
  };

  // 모드 진입 후 자동으로 레포 목록 시도 (사용자 클릭 줄이기 위해)
  useEffect(() => {
    if (step === 2 && repoList.length === 0 && !repoLoading) {
      loadRepos();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step]);

  const filteredRepos = repoList.filter(
    (r) => !repoSearch || r.full_name.toLowerCase().includes(repoSearch.toLowerCase())
  );

  const proceedDisabled = !selectedRepo;

  return (
    <div
      className="fixed inset-0 z-[7500] flex items-center justify-center animate-fade-in"
      style={{ background: "rgba(0,0,0,0.7)", backdropFilter: "blur(14px)" }}
    >
      <div
        className={`relative w-[760px] max-h-[90vh] rounded-2xl border shadow-[0_40px_100px_rgba(0,0,0,0.6)] flex flex-col overflow-hidden ${
          isDarkMode ? "bg-[#0f1219] border-white/10" : "bg-white border-slate-200"
        }`}
      >
        {/* Header */}
        <div
          className={`flex items-center justify-between px-7 py-5 border-b shrink-0 ${
            isDarkMode ? "border-white/5" : "border-slate-100"
          }`}
        >
          <div className="flex items-center gap-3">
            {step === 2 && (
              <button
                onClick={() => setStep(1)}
                title="모드 다시 선택"
                className={`w-8 h-8 flex items-center justify-center rounded-lg transition-colors ${
                  isDarkMode ? "hover:bg-white/10 text-slate-400" : "hover:bg-slate-100 text-slate-500"
                }`}
              >
                <ArrowLeft size={14} />
              </button>
            )}
            <div className="flex flex-col leading-tight">
              <span className="text-[10px] font-black text-blue-400 uppercase tracking-[0.3em]">
                NAVIGATOR
              </span>
              <h2 className={`text-[18px] font-black tracking-tight ${isDarkMode ? "text-white" : "text-slate-900"}`}>
                {step === 1 ? "어떻게 시작할까요?" : `${MODES.find((m) => m.key === pickedMode)?.label} — 레포지토리 선택`}
              </h2>
            </div>
          </div>
          {/* CREATE는 이미 dismiss했고 UPDATE/REVERSE에서는 X로 닫지 못하게 (모드는 의무 선택) */}
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto custom-scrollbar p-7">
          {step === 1 ? (
            <Step1ModeSelect modes={MODES} onPick={pickMode} isDarkMode={isDarkMode} />
          ) : (
            <Step2GithubPick
              isDarkMode={isDarkMode}
              authToken={authToken}
              selectedRepo={selectedRepo}
              repoList={filteredRepos}
              repoLoading={repoLoading}
              repoSearch={repoSearch}
              setRepoSearch={setRepoSearch}
              repoScopeError={repoScopeError}
              onReloadRepos={loadRepos}
              onSelectRepo={selectRepo}
              branchList={branchList}
              branchLoading={branchLoading}
              githubBranch={githubBranch}
              setGithubBranch={setGithubBranch}
              onLoadBranches={loadBranches}
            />
          )}
        </div>

        {/* Footer (Step 2만) */}
        {step === 2 && (
          <div
            className={`flex items-center justify-between px-7 py-4 border-t shrink-0 ${
              isDarkMode ? "border-white/5" : "border-slate-100"
            }`}
          >
            <p className={`text-[11px] ${isDarkMode ? "text-slate-500" : "text-slate-400"}`}>
              나중에 라이브러리에서 다른 세션으로 전환할 수 있습니다.
            </p>
            <button
              onClick={dismiss}
              disabled={proceedDisabled}
              className={`flex items-center gap-2 px-5 py-2 rounded-lg text-[13px] font-bold transition-all ${
                proceedDisabled
                  ? "bg-white/5 text-slate-500 cursor-not-allowed"
                  : "bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white shadow-lg shadow-blue-500/20"
              }`}
            >
              메인으로 이동
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Step 1: 모드 선택 ─────────────────────────────────────
function Step1ModeSelect({ modes, onPick, isDarkMode }) {
  return (
    <div className="flex flex-col gap-3">
      <p className={`text-[13px] mb-3 ${isDarkMode ? "text-slate-400" : "text-slate-600"}`}>
        시작하려는 작업의 성격을 골라주세요. CREATE는 GitHub 없이 곧바로 대화로 시작합니다.
      </p>
      {modes.map((mode) => (
        <button
          key={mode.key}
          onClick={() => onPick(mode.key)}
          className={`group text-left flex items-start gap-4 p-5 rounded-2xl border transition-all hover:scale-[1.01] ${
            isDarkMode
              ? "bg-white/[0.03] border-white/5 hover:border-blue-400/40 hover:bg-white/[0.06]"
              : "bg-slate-50 border-slate-100 hover:border-blue-300 hover:bg-white"
          }`}
        >
          <div
            className={`w-12 h-12 rounded-xl bg-gradient-to-br ${mode.color} flex items-center justify-center shrink-0 shadow-lg group-hover:scale-110 transition-transform`}
          >
            <mode.icon className="text-white w-6 h-6" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-baseline gap-2 mb-1">
              <h3 className={`text-[15px] font-black ${isDarkMode ? "text-white" : "text-slate-900"}`}>
                {mode.label}
              </h3>
              <span className={`text-[10px] font-bold uppercase tracking-[0.2em] ${isDarkMode ? "text-blue-400" : "text-blue-600"}`}>
                {mode.sub}
              </span>
            </div>
            <p className={`text-[12.5px] leading-relaxed ${isDarkMode ? "text-slate-400" : "text-slate-600"}`}>
              {mode.desc}
            </p>
          </div>
        </button>
      ))}
    </div>
  );
}

// ── Step 2: GitHub 레포 + 브랜치 선택 ─────────────────────
function Step2GithubPick({
  isDarkMode, authToken,
  selectedRepo, repoList, repoLoading, repoSearch, setRepoSearch,
  repoScopeError, onReloadRepos, onSelectRepo,
  branchList, branchLoading, githubBranch, setGithubBranch, onLoadBranches,
}) {
  return (
    <div className="flex flex-col gap-5">
      <p className={`text-[13px] ${isDarkMode ? "text-slate-400" : "text-slate-600"}`}>
        분석할 GitHub 레포지토리와 브랜치를 선택해주세요. 한 번 설정하면 메인 화면에서 그대로 사용됩니다.
      </p>

      {!authToken && (
        <div className="px-4 py-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400 text-[12px]">
          GitHub 로그인 토큰이 없어 레포 목록을 불러올 수 없습니다. 설정에서 GitHub를 다시 연결해주세요.
        </div>
      )}

      {repoScopeError && (
        <div className="px-4 py-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400 text-[12px]">
          GitHub 재연결이 필요합니다. 우측 아바타 메뉴 → GitHub 연동에서 연결을 갱신하세요.
        </div>
      )}

      {/* 선택된 레포 */}
      <div className={`rounded-xl border ${isDarkMode ? "bg-white/[0.03] border-white/5" : "bg-slate-50 border-slate-100"}`}>
        <div className="flex items-center gap-3 px-4 py-3">
          <div className="flex-1 min-w-0">
            {selectedRepo ? (
              <div className="flex items-center gap-2 flex-wrap">
                <GitBranch size={15} className="text-slate-400 shrink-0" />
                <span className={`text-sm font-bold truncate ${isDarkMode ? "text-slate-100" : "text-slate-800"}`}>
                  {selectedRepo.full_name}
                </span>
                {selectedRepo.private && (
                  <span className="text-[10px] text-amber-400 border border-amber-400/30 px-1.5 py-0.5 rounded">
                    private
                  </span>
                )}
              </div>
            ) : (
              <span className={`text-sm ${isDarkMode ? "text-slate-500" : "text-slate-400"}`}>
                선택된 레포지토리가 없습니다
              </span>
            )}
          </div>
          <button
            onClick={onReloadRepos}
            disabled={repoLoading || !authToken}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors disabled:opacity-40 ${
              isDarkMode
                ? "bg-white/5 hover:bg-white/10 border border-white/10 text-slate-200"
                : "bg-white hover:bg-slate-50 border border-slate-200 text-slate-700"
            }`}
          >
            {repoLoading ? <Loader2 size={13} className="animate-spin" /> : <GitBranch size={13} />}
            <span>{repoList.length > 0 ? "다시 불러오기" : "레포 불러오기"}</span>
          </button>
        </div>

        {/* 레포 검색 + 리스트 */}
        {repoList.length > 0 && (
          <>
            <div className={`px-3 py-2 border-t ${isDarkMode ? "border-white/5" : "border-slate-200"}`}>
              <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg ${isDarkMode ? "bg-white/5" : "bg-white"}`}>
                <Search size={13} className="text-slate-500 shrink-0" />
                <input
                  value={repoSearch}
                  onChange={(e) => setRepoSearch(e.target.value)}
                  placeholder="레포 검색..."
                  className="flex-1 bg-transparent text-sm focus:outline-none placeholder:text-slate-400"
                />
              </div>
            </div>
            <ul className={`max-h-52 overflow-y-auto custom-scrollbar divide-y ${isDarkMode ? "divide-white/5" : "divide-slate-100"}`}>
              {repoList.map((repo) => (
                <li
                  key={repo.full_name}
                  onClick={() => onSelectRepo(repo)}
                  className={`flex items-center gap-2 px-4 py-2.5 cursor-pointer transition-colors ${
                    isDarkMode ? "hover:bg-white/5" : "hover:bg-slate-50"
                  } ${selectedRepo?.full_name === repo.full_name ? (isDarkMode ? "bg-blue-500/10" : "bg-blue-50") : ""}`}
                >
                  <GitBranch size={13} className="text-slate-500 shrink-0" />
                  <span className={`text-sm font-medium truncate flex-1 ${isDarkMode ? "text-slate-200" : "text-slate-700"}`}>
                    {repo.name}
                  </span>
                  <span className="text-xs text-slate-500 shrink-0">{repo.owner}</span>
                  {repo.private && <span className="text-[10px] text-amber-400 shrink-0">private</span>}
                </li>
              ))}
            </ul>
          </>
        )}
      </div>

      {/* 브랜치 picker */}
      {selectedRepo && (
        <div className={`rounded-xl border ${isDarkMode ? "bg-white/[0.03] border-white/5" : "bg-slate-50 border-slate-100"}`}>
          <div className="flex items-center gap-3 px-4 py-3">
            <GitBranch size={14} className="text-slate-400 shrink-0" />
            <span className={`text-xs font-bold shrink-0 ${isDarkMode ? "text-slate-400" : "text-slate-500"}`}>
              브랜치
            </span>
            {branchLoading ? (
              <div className="flex items-center gap-2 flex-1">
                <Loader2 size={13} className="animate-spin text-slate-500" />
                <span className="text-xs text-slate-500">로드 중...</span>
              </div>
            ) : branchList.length > 0 ? (
              <select
                value={typeof githubBranch === "object" && githubBranch !== null ? githubBranch.name : githubBranch || ""}
                onChange={(e) => setGithubBranch(e.target.value)}
                style={{ colorScheme: isDarkMode ? "dark" : "light" }}
                className={`flex-1 rounded-lg px-3 py-1.5 text-sm transition-colors cursor-pointer border outline-none ${
                  isDarkMode
                    ? "bg-[#1a1a2e] border-white/10 text-slate-200 focus:border-white/30"
                    : "bg-white border-slate-200 text-slate-800 focus:border-blue-400"
                }`}
              >
                {branchList.map((b) => {
                  const name = typeof b === "object" && b !== null ? b.name : b;
                  const isProtected = typeof b === "object" && b !== null ? b.protected : false;
                  return (
                    <option key={name} value={name}>
                      {name}{isProtected ? " 🔒" : ""}
                    </option>
                  );
                })}
              </select>
            ) : (
              <div className="flex items-center gap-2 flex-1">
                <input
                  type="text"
                  value={githubBranch || "main"}
                  onChange={(e) => setGithubBranch(e.target.value)}
                  placeholder="브랜치명 (예: main)"
                  className={`flex-1 rounded-lg px-3 py-1.5 text-sm outline-none border ${
                    isDarkMode
                      ? "bg-white/5 border-white/10 text-slate-200 placeholder:text-slate-500"
                      : "bg-white border-slate-200 text-slate-800 placeholder:text-slate-400"
                  }`}
                />
                <button
                  onClick={() => onLoadBranches(selectedRepo.owner, selectedRepo.name)}
                  className={`px-2 py-1.5 rounded-lg text-xs transition-colors ${
                    isDarkMode ? "bg-white/5 hover:bg-white/10 text-slate-400" : "bg-white hover:bg-slate-100 text-slate-500 border border-slate-200"
                  }`}
                >
                  재시도
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
