/**
 * API Client — HTTP 요청 공통 처리 및 베이스 설정
 */

const BASE_URL = "http://127.0.0.1";

export async function request(port, path, options = {}) {
  const url = `${BASE_URL}:${port}${path}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(errorBody.message || `API Error: ${response.status}`);
  }

  return response.json();
}
