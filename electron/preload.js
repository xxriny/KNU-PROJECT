/**
 *
 * contextBridge를 통해 렌더러 프로세스(React)에
 * 안전한 API를 노출한다.
 *
 * React에서 사용:
 *   const port = await window.electronAPI.getBackendPort();
 *   const ws = new WebSocket(`ws://127.0.0.1:${port}/ws/pipeline`);
 */

const { contextBridge, ipcRenderer } = require("electron");

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
});
