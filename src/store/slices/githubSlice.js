const STORAGE_KEY = "navigator_github";

function load() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function save(data) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } catch {}
}

const stored = load();

export const createGithubSlice = (set, get) => ({
  githubToken: stored.token || "",
  githubOwner: stored.owner || "",
  githubRepo: stored.repo || "",
  githubBranch: stored.branch || "main",

  setGithubSettings: (token, owner, repo, branch) => {
    const br = branch || stored.branch || "main";
    save({ token, owner, repo, branch: br });
    set({ githubToken: token, githubOwner: owner, githubRepo: repo, githubBranch: br });
  },

  setGithubBranch: (branch) => {
    const current = load();
    save({ ...current, branch });
    set({ githubBranch: branch });
  },

  clearGithubSettings: () => {
    save({});
    set({ githubToken: "", githubOwner: "", githubRepo: "", githubBranch: "main" });
  },
});
