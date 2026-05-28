/**
 *
 * contextBridge를 통해 렌더러 프로세스(React)에
 * 안전한 API를 노출한다.
 *
 * React에서 사용:
 *   const port = await window.electronAPI.getBackendPort();
 *   const ws = new WebSocket(`ws://127.0.0.1:${port}/ws/pipeline`);
 */

const { contextBridge, ipcRenderer, webFrame } = require("electron");

// 렌더러 zoom을 1:1로 고정 — OS DPI 배율(125% 등)이 렌더러까지 전파되는 것을 차단.
// force-device-scale-factor(main)와 함께 써야 완전히 고정됨.
webFrame.setZoomFactor(1.0);
webFrame.setVisualZoomLevelLimits(1, 1);

contextBridge.exposeInMainWorld("electronAPI", {
  /**
   * Python 백엔드의 동적 포트 번호를 가져온다.
   * @returns {Promise<number>} 포트 번호
   */
  getBackendPort: () => ipcRenderer.invoke("get-backend-port"),

  /**
   * Python 백엔드의 상태를 가져온다.
   * @returns {Promise<{port: number, running: boolean}>}
   */
  getBackendStatus: () => ipcRenderer.invoke("get-backend-status"),

  /**
   * 로컬 폴더 선택 다이얼로그를 열고 선택된 경로를 반환한다.
   * @returns {Promise<string|null>} 선택된 폴더 절대 경로, 취소 시 null
   */
  selectFolder: () => ipcRenderer.invoke("select-folder"),
  /**
   * 윈도우 타이틀 바 테마를 동적으로 변경한다 (Windows TitleBarOverlay 대응).
   * @param {boolean} isDark - 다크 모드 여부
   */
  setTitleBarTheme: (isDark) => ipcRenderer.invoke("set-titlebar-theme", isDark),

  /**
   * GitHub OAuth 인증 URL을 시스템 기본 브라우저로 연다.
   * @param {string} url - GitHub OAuth authorize URL
   */
  openGithubAuth: (url) => ipcRenderer.invoke("github-oauth-open", url),

  /** 로그인 완료 후 메인 프로세스에서 창을 새로고침 */
  reloadWindow: () => ipcRenderer.invoke("reload-window"),

  /**
   * GitHub OAuth 콜백 수신 리스너 등록.
   * navigator://auth/callback?code=...&state=... 콜백이 오면 cb({ code, state }) 호출.
   * @param {function} cb
   */
  onGithubAuthCallback: (cb) =>
    ipcRenderer.on("github-auth-callback", (_, data) => cb(data)),

  /** onGithubAuthCallback 리스너 해제 */
  removeGithubAuthCallback: () =>
    ipcRenderer.removeAllListeners("github-auth-callback"),

  /** 업데이트 가능 알림 수신 */
  onUpdateAvailable: (cb) =>
    ipcRenderer.on("update-available", (_, info) => cb(info)),

  /** 업데이트 다운로드 완료 알림 수신 */
  onUpdateDownloaded: (cb) =>
    ipcRenderer.on("update-downloaded", (_, info) => cb(info)),

  /** 업데이트 설치 및 재시작 */
  installUpdate: () => ipcRenderer.invoke("install-update"),
});
