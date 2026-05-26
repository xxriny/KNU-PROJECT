/**
 * serverClient — Cloud Run navigator-server 전용 HTTP 클라이언트
 */

export const SERVER_URL = "https://navigator-server-640700885251.asia-northeast3.run.app";

export async function serverRequest(path, options = {}) {
  const url = `${SERVER_URL}${path}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(errorBody.detail || errorBody.message || `Server Error: ${response.status}`);
  }

  return response.json();
}
