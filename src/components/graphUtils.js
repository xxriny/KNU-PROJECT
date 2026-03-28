/**
 * 그래프 데이터 유틸리티 — 그룹화, 중복 제거, 레이블 축약, degree 맵
 */

export function groupBy(items, keyFn) {
  const grouped = {};
  for (const item of items) {
    const key = keyFn(item);
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push(item);
  }
  return grouped;
}

export function dedupeEdges(edges) {
  const map = new Map();
  for (const edge of edges) {
    const key = `${edge.source}|${edge.target}|${edge.type || "edge"}`;
    if (!map.has(key)) map.set(key, edge);
  }
  return [...map.values()];
}

export function compactPathLabel(text = "") {
  const value = String(text || "");
  if (!value) return "-";
  const cleaned = value.replace(/^핵심 분석 모듈:\s*/i, "").trim();
  const slash = cleaned.split("/");
  if (slash.length >= 2) {
    return `${slash[slash.length - 2]}/${slash[slash.length - 1]}`;
  }
  return cleaned.length > 40 ? `${cleaned.slice(0, 37)}...` : cleaned;
}

export function buildDegreeMap(edges = []) {
  const degree = {};
  for (const edge of edges) {
    degree[edge.source] = (degree[edge.source] || 0) + 1;
    degree[edge.target] = (degree[edge.target] || 0) + 1;
  }
  return degree;
}
