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

  setGithubSettings: (token, owner, repo) => {
    save({ token, owner, repo });
    set({ githubToken: token, githubOwner: owner, githubRepo: repo });
  },

  clearGithubSettings: () => {
    save({});
    set({ githubToken: "", githubOwner: "", githubRepo: "" });
  },
});
