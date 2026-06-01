/**
 *
 * 역할:
 * 1. 사용 가능한 빈 포트를 동적으로 할당
 * 2. child_process.spawn으로 Python FastAPI 백엔드를 백그라운드 실행
 * 3. 백엔드 /health 엔드포인트 폴링으로 준비 완료 확인
 * 4. BrowserWindow 생성 및 React 앱 로드
 * 5. IPC를 통해 포트 번호를 렌더러 프로세스에 전달
 * 6. 앱 종료 시 Python 자식 프로세스 안전 종료
 *
 * 수정 (v2.2):
 * - EPIPE broken pipe 수정: stdout/stderr 데이터 핸들러에 try/catch 추가
 * - 프로세스 종료 시 stdout/stderr 리스너 제거 후 파이프 닫기
 * - process.stdout.write 대신 console.log 사용 시 EPIPE 방어 처리
 * - pythonProcess.stdout/stderr에 'error' 이벤트 핸들러 추가
 *
 * 수정 (v2.3 — macOS 지원):
 * - PyInstaller 번들 바이너리 우선 탐색 (dist/navigator-backend/navigator-backend)
 * - macOS: titleBarStyle "hiddenInset" + setTitleBarOverlay 호출 비활성화
 * - NAVIGATOR_BACKEND_ROOT / NAVIGATOR_STORAGE_DIR 환경변수 주입
 *   (PyInstaller frozen 모드에서 __file__ 기반 경로 탐색이 불가하므로)
 */

const { app, BrowserWindow, ipcMain, Menu, dialog, nativeTheme, shell } = require("electron");
const { spawn } = require("child_process");
const path = require("path");
const net = require("net");
const http = require("http");
const fs = require("fs");
const { autoUpdater } = require("electron-updater");

// OS 디스플레이 배율(125%, 150% 등)을 무시하고 항상 1:1 픽셀로 렌더링.
// zoomFactor만으로는 OS-level DPI 스케일링을 막을 수 없어 commandLine 플래그가 필요.
app.commandLine.appendSwitch("force-device-scale-factor", "1");

// ── GitHub OAuth 커스텀 프로토콜 ─────────────────────────────
// Windows에서 navigator:// 콜백을 받으려면 single-instance lock이 필요
const PROTOCOL = "navigator";

// 개발 모드에서는 Electron 실행 파일 경로를 명시해야 setAsDefaultProtocolClient가 동작
if (process.defaultApp && process.argv.length >= 2) {
  app.setAsDefaultProtocolClient(PROTOCOL, process.execPath, [path.resolve(process.argv[1])]);
} else {
  app.setAsDefaultProtocolClient(PROTOCOL);
}

// Windows: 두 번째 인스턴스가 실행되면 콜백 URL이 commandLine에 담겨 옴
const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
  app.quit();
  process.exit(0);
}

// ── 상태 ────────────────────────────────
let mainWindow = null;
let pythonProcess = null;
let backendPort = null;
let isQuitting = false;  // 앱 종료 중 플래그

// ── GitHub OAuth 콜백 처리 ───────────────────────────────────
function handleProtocolCallback(url) {
  if (!url || !url.startsWith(`${PROTOCOL}://`)) return;
  try {
    const parsed = new URL(url);
    if (parsed.pathname !== "//auth/callback" && parsed.host !== "auth") return;
    const code = parsed.searchParams.get("code");
    const state = parsed.searchParams.get("state");
    if (code && mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send("github-auth-callback", { code, state });
      mainWindow.focus();
    }
  } catch (e) {
    safeError("[Electron] Protocol URL parse error:", e.message);
  }
}

// ── 개발/프로덕션 경로 ──────────────────
const isDev = !app.isPackaged;
const BACKEND_DIR = isDev
  ? path.join(__dirname, "..", "backend")
  : path.join(process.resourcesPath, "backend");

// ── EPIPE 방어: process.stdout/stderr 전역 오류 핸들러 ──
// Electron 메인 프로세스의 stdout이 닫혔을 때 EPIPE로 크래시하지 않도록 방어
process.stdout.on("error", (err) => {
  if (err.code === "EPIPE") return; // 무시
});
process.stderr.on("error", (err) => {
  if (err.code === "EPIPE") return; // 무시
});

// ── 안전한 로그 함수 ─────────────────────
function safeLog(...args) {
  try {
    console.log(...args);
  } catch (e) {
    // EPIPE 등 stdout 오류 무시
  }
}

function safeError(...args) {
  try {
    console.error(...args);
  } catch (e) {
    // EPIPE 등 stderr 오류 무시
  }
}

// ═══════════════════════════════════════════
//  포트 할당
// ═══════════════════════════════════════════

/**
 * 사용 가능한 빈 포트를 동적으로 찾는다.
 * OS가 임시 포트를 할당하도록 0번 포트에 바인딩 후 즉시 해제.
 */
function findFreePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.listen(0, "127.0.0.1", () => {
      const port = server.address().port;
      server.close(() => resolve(port));
    });
    server.on("error", reject);
  });
}

// ═══════════════════════════════════════════
//  Python 백엔드 프로세스 관리
// ═══════════════════════════════════════════

/**
 * Python FastAPI 백엔드를 자식 프로세스로 실행.
 *
 * 우선순위:
 *   1. PyInstaller 번들 바이너리 (dist/navigator-backend/navigator-backend)
 *      — macOS 프로덕션 빌드. Python 인터프리터 없이 직접 실행.
 *   2. Windows Embeddable Python (.python/python.exe)
 *      — Windows 프로덕션 빌드 (build-prod.cjs가 설치).
 *   3. .venv Python — 개발 환경.
 *   4. 시스템 Python — 최후 폴백.
 *
 * @param {number} port - 할당된 포트 번호
 */
function startPythonBackend(port) {
  const isWin = process.platform === "win32";

  // 1) PyInstaller 번들 바이너리 (macOS/Linux 프로덕션)
  const pyinstallerBin = path.join(
    BACKEND_DIR, "dist", "navigator-backend",
    isWin ? "navigator-backend.exe" : "navigator-backend"
  );

  // 2) Embeddable Python (Windows 프로덕션)
  const bundledPython = isWin
    ? path.join(BACKEND_DIR, ".python", "python.exe")
    : path.join(BACKEND_DIR, ".python", "bin", "python");

  // 3) venv Python (개발 환경)
  const venvPython = isWin
    ? path.join(BACKEND_DIR, ".venv", "Scripts", "python.exe")
    : path.join(BACKEND_DIR, ".venv", "bin", "python");

  const fallbackCmd = isWin ? "python" : "python3";

  // PyInstaller frozen 모드에서 __file__ 기반 경로가 bundle 내부를 가리키므로
  // 올바른 backend 루트 디렉토리를 환경변수로 명시 전달.
  const commonEnv = {
    ...process.env,
    PYTHONUNBUFFERED: "1",
    PYTHONIOENCODING: "utf-8",
    NAVIGATOR_BACKEND_ROOT: BACKEND_DIR,
    // NAVIGATOR_STORAGE_DIR: 사용자가 별도 지정한 경우 덮어쓰지 않음
    NAVIGATOR_STORAGE_DIR: process.env.NAVIGATOR_STORAGE_DIR
      || path.join(BACKEND_DIR, "storage"),
  };

  if (fs.existsSync(pyinstallerBin)) {
    // PyInstaller 번들: Python 인터프리터 없이 직접 실행
    safeLog(`[Electron] Using PyInstaller bundle: ${pyinstallerBin}`);
    pythonProcess = spawn(pyinstallerBin, ["--port", String(port)], {
      cwd: BACKEND_DIR,
      stdio: ["ignore", "pipe", "pipe"],
      env: commonEnv,
    });
  } else {
    // Python 인터프리터 + main.py 실행
    const pythonCmd = fs.existsSync(bundledPython)
      ? bundledPython
      : fs.existsSync(venvPython)
        ? venvPython
        : fallbackCmd;
    const mainScript = path.join(BACKEND_DIR, "main.py");

    safeLog(`[Electron] Starting Python backend using ${pythonCmd} on port ${port}...`);
    safeLog(`[Electron] Script: ${mainScript}`);

    pythonProcess = spawn(pythonCmd, ["main.py", "--port", String(port)], {
      cwd: BACKEND_DIR,
      stdio: ["ignore", "pipe", "pipe"],
      env: {
        ...commonEnv,
        PYTHONPATH: BACKEND_DIR,   // Embeddable Python은 cwd를 sys.path에 추가 안 함
      },
    });
  }

  // stdout 스트림 오류 방어 (EPIPE 핵심 수정)
  pythonProcess.stdout.on("error", (err) => {
    if (err.code !== "EPIPE") {
      safeError(`[Python stdout error] ${err.message}`);
    }
  });

  pythonProcess.stderr.on("error", (err) => {
    if (err.code !== "EPIPE") {
      safeError(`[Python stderr error] ${err.message}`);
    }
  });

  // 데이터 핸들러 — try/catch로 EPIPE 방어
  pythonProcess.stdout.on("data", (data) => {
    if (isQuitting) return;
    try {
      const text = data.toString("utf8").trim();
      if (text) safeLog(`[Python] ${text}`);
    } catch (e) {
      // 무시
    }
  });

  pythonProcess.stderr.on("data", (data) => {
    if (isQuitting) return;
    try {
      const text = data.toString("utf8").trim();
      if (text) safeError(`[Python ERR] ${text}`);
    } catch (e) {
      // 무시
    }
  });

  pythonProcess.on("close", (code) => {
    safeLog(`[Electron] Python process exited with code ${code}`);
    pythonProcess = null;
  });

  pythonProcess.on("error", (err) => {
    safeError(`[Electron] Failed to start Python:`, err.message);
    pythonProcess = null;
  });
}

/**
 * Python 백엔드가 준비될 때까지 /health 엔드포인트를 폴링.
 * 최대 30초 대기 후 타임아웃.
 */
function waitForBackend(port, maxRetries = 240, interval = 500) {
  return new Promise((resolve, reject) => {
    let attempts = 0;

    const check = () => {
      attempts++;
      const req = http.get(`http://127.0.0.1:${port}/health`, (res) => {
        // 응답 데이터를 소비해야 keep-alive 연결이 정상 종료됨
        res.resume();
        if (res.statusCode === 200) {
          safeLog(`[Electron] Backend ready on port ${port} (attempt ${attempts})`);
          resolve();
        } else {
          retry();
        }
      });

      req.on("error", () => retry());
      req.setTimeout(1000, () => {
        req.destroy();
        retry();
      });
    };

    const retry = () => {
      if (attempts >= maxRetries) {
        reject(new Error(`Backend failed to start after ${maxRetries} attempts`));
      } else {
        setTimeout(check, interval);
      }
    };

    check();
  });
}

/**
 * Python 자식 프로세스를 안전하게 종료.
 * 종료 전 stdout/stderr 파이프를 먼저 닫아 EPIPE 방지.
 */
function killPythonProcess() {
  if (!pythonProcess) return;

  safeLog("[Electron] Killing Python backend...");
  isQuitting = true;

  try {
    // stdout/stderr 리스너 제거 및 파이프 닫기 (EPIPE 핵심 수정)
    if (pythonProcess.stdout) {
      pythonProcess.stdout.removeAllListeners("data");
      pythonProcess.stdout.destroy();
    }
    if (pythonProcess.stderr) {
      pythonProcess.stderr.removeAllListeners("data");
      pythonProcess.stderr.destroy();
    }

    if (process.platform === "win32") {
      // Windows: taskkill로 프로세스 트리 전체 종료
      const killer = spawn("taskkill", ["/pid", String(pythonProcess.pid), "/f", "/t"], {
        stdio: "ignore",
        detached: true,
      });
      killer.unref();
    } else {
      pythonProcess.kill("SIGTERM");
      // 3초 후 강제 종료
      setTimeout(() => {
        if (pythonProcess) {
          try { pythonProcess.kill("SIGKILL"); } catch (e) {}
        }
      }, 3000);
    }
  } catch (err) {
    safeError("[Electron] Error killing Python:", err.message);
  }

  pythonProcess = null;
}

// ═══════════════════════════════════════════
//  Electron 윈도우 생성
// ═══════════════════════════════════════════

function createWindow() {
  const isMac = process.platform === "darwin";

  // titleBarOverlay (Windows 전용 — 색상/아이콘 커스텀 타이틀바)
  // macOS는 titleBarStyle "hiddenInset"으로 트래픽 라이트 버튼을 유지
  const titleBarOptions = isMac
    ? { titleBarStyle: "hiddenInset" }
    : {
        titleBarStyle: "hidden",
        titleBarOverlay: {
          color: "#0D1117",
          symbolColor: "#8B949E",
          height: 56,
        },
      };

  mainWindow = new BrowserWindow({
    width: 1600,
    height: 1000,
    minWidth: 1200,
    minHeight: 700,
    title: "NAVIGATOR",
    backgroundColor: "#0D1117",
    ...titleBarOptions,
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
      zoomFactor: 1.0,
    },
  });

  // 개발 모드: Vite dev server / 프로덕션: 빌드된 index.html
  if (isDev) {
    mainWindow.loadURL("http://localhost:5173");
    // DevTools는 별도 창으로 열지 않음 (EPIPE 원인 중 하나)
    // mainWindow.webContents.openDevTools({ mode: "detach" });
  } else {
    mainWindow.loadFile(path.join(__dirname, "..", "dist", "index.html"));
  }

  mainWindow.on("closed", () => {
    mainWindow = null;
  });

  // 페이지 로드 후 zoom이 리셋되는 경우를 방어 (일부 Electron 버전에서 발생).
  mainWindow.webContents.on("did-finish-load", () => {
    mainWindow.webContents.setZoomFactor(1.0);
    mainWindow.webContents.setVisualZoomLevelLimits(1, 1);
  });

  // 최대화
  mainWindow.maximize();

  // 최상단 메뉴바 완전 제거
  Menu.setApplicationMenu(null);
}

// ─── second-instance: Windows에서 navigator:// 콜백 수신 ─────
app.on("second-instance", (event, commandLine) => {
  const url = commandLine.find((arg) => arg.startsWith(`${PROTOCOL}://`));
  if (url) handleProtocolCallback(url);
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.focus();
  }
});

// ─── open-url: macOS / Linux ─────────────────────────────────
app.on("open-url", (event, url) => {
  event.preventDefault();
  handleProtocolCallback(url);
});

// ═══════════════════════════════════════════
//  IPC Handlers
// ═══════════════════════════════════════════

// 렌더러가 백엔드 포트 번호를 요청
ipcMain.handle("get-backend-port", () => {
  return backendPort;
});

// 로컬 폴더 선택 다이얼로그
ipcMain.handle("select-folder", async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ["openDirectory"],
    title: "프로젝트 폴더 선택",
  });
  return result.canceled ? null : result.filePaths[0];
});

// 타이틀 바 오버레이 테마 실시간 업데이트 (Windows 전용 — macOS는 네이티브 처리)
ipcMain.handle("set-titlebar-theme", (event, isDark) => {
  if (!mainWindow || process.platform === "darwin") return;

  safeLog(`[Electron] Received theme update request: isDark=${isDark}`);

  try {
    nativeTheme.themeSource = isDark ? "dark" : "light";

    const themeColors = isDark
      ? { color: "#0D1117", symbolColor: "#8B949E" }
      : { color: "#F1F5F9", symbolColor: "#475569" };

    mainWindow.setTitleBarOverlay({
      ...themeColors,
      height: 56,
    });
  } catch (err) {
    safeError("[Electron] Failed to update title bar overlay:", err.message);
  }
});

// 렌더러가 백엔드 상태를 요청
ipcMain.handle("get-backend-status", () => {
  return {
    port: backendPort,
    running: pythonProcess !== null,
  };
});

// GitHub OAuth: 시스템 브라우저로 GitHub 인증 URL 열기
ipcMain.handle("github-oauth-open", async (event, url) => {
  await shell.openExternal(url);
});

// 로그인 완료 후 렌더러 새로고침
ipcMain.handle("reload-window", () => {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.reload();
  }
});

// ═══════════════════════════════════════════
//  앱 라이프사이클
// ═══════════════════════════════════════════

// ═══════════════════════════════════════════
//  Auto Updater
// ═══════════════════════════════════════════

function setupAutoUpdater() {
  if (isDev) return; // 개발 모드에서는 업데이트 비활성화

  autoUpdater.autoDownload = true;
  autoUpdater.autoInstallOnAppQuit = true;

  autoUpdater.on("update-available", (info) => {
    safeLog(`[Updater] 새 버전 발견: ${info.version}`);
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send("update-available", info);
    }
  });

  autoUpdater.on("update-downloaded", (info) => {
    safeLog(`[Updater] 다운로드 완료: ${info.version}`);
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send("update-downloaded", info);
    }
  });

  autoUpdater.on("error", (err) => {
    safeError("[Updater] 오류:", err.message);
  });

  // 앱 시작 5초 후 업데이트 확인 (백엔드 준비 후)
  setTimeout(() => autoUpdater.checkForUpdates(), 5000);

  // 이후 6시간마다 재확인
  setInterval(() => autoUpdater.checkForUpdates(), 6 * 60 * 60 * 1000);
}

ipcMain.handle("install-update", () => {
  autoUpdater.quitAndInstall();
});

app.whenReady().then(async () => {
  try {
    // 1. 빈 포트 할당
    backendPort = await findFreePort();
    safeLog(`[Electron] Allocated port: ${backendPort}`);

    // 2. Python 백엔드 실행
    startPythonBackend(backendPort);

    // 3. 백엔드 준비 대기
    await waitForBackend(backendPort);

    // 4. 윈도우 생성
    createWindow();

    // 5. 자동 업데이트 설정
    setupAutoUpdater();
  } catch (err) {
    safeError("[Electron] Startup failed:", err.message);
    app.quit();
  }
});

// macOS: 모든 윈도우가 닫혀도 앱은 유지
app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

// 모든 윈도우 닫힘 → 앱 종료
app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

// 앱 종료 전 Python 프로세스 정리
app.on("before-quit", () => {
  killPythonProcess();
});

// 앱 완전 종료 시 최종 정리
app.on("will-quit", () => {
  killPythonProcess();
});
