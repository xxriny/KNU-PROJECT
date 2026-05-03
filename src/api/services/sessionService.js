import { request } from "../apiClient";

export const sessionService = {
  /** 세션 복구 (RAG 데이터 기반) */
  async restoreSession(port, runId) {
    return request(port, `/api/session/${runId}/restore`);
  },

  /** 세션 삭제 */
  async deleteSession(port, runId) {
    return request(port, `/api/session/${runId}`, { method: "DELETE" });
  },

  /** 메모(메모) 목록 조회 */
  async getMemos(port, sessionId) {
    const query = sessionId ? `?session_id=${sessionId}` : "";
    return request(port, `/api/memos${query}`);
  },

  /** 메모 추가 */
  async addMemo(port, memoData) {
    return request(port, "/api/memos", {
      method: "POST",
      body: JSON.stringify(memoData),
    });
  },

  /** 메모 삭제 */
  async removeMemo(port, memoId) {
    return request(port, `/api/memos/${memoId}`, { method: "DELETE" });
  }
};
