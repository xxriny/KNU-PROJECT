import { request } from "../apiClient";

export const fileService = {
  /** 폴더 스캔 */
  async scanFolder(port, path, maxDepth = 3) {
    return request(port, "/api/scan-folder", {
      method: "POST",
      body: JSON.stringify({ path, max_depth: maxDepth }),
    });
  },

  /** 파일 읽기 */
  async readFile(port, path) {
    return request(port, "/api/read-file", {
      method: "POST",
      body: JSON.stringify({ path }),
    });
  },

  /** 파일 쓰기 (필요 시) */
  async writeFile(port, path, content) {
    return request(port, "/api/write-file", {
      method: "POST",
      body: JSON.stringify({ path, content }),
    });
  }
};
