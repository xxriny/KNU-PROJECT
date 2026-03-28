/**
 * ResultViewer 공유 유틸리티 함수
 */

export function toCompactModuleLabel(text) {
  const raw = String(text || "").trim();
  if (!raw) return "설명 없음";
  return raw
    .replace(/^핵심\s*분석\s*모듈\s*:\s*/i, "")
    .replace(/^핵심\s*모듈\s*:\s*/i, "")
    .replace(/^분석\s*모듈\s*:\s*/i, "");
}

export function buildReqFunctionNameMap(mapped_requirements) {
  const map = {};
  for (const req of mapped_requirements || []) {
    const reqId = req?.REQ_ID || req?.req_id;
    if (!reqId) continue;
    const functionName = String(
      req?.functional_name || req?.label || toCompactModuleLabel(req?.description) || req?.name || ""
    ).trim();
    if (functionName) {
      map[reqId] = functionName;
    }
  }
  return map;
}

export function layerBadgeTone(layer) {
  const key = String(layer || "").toLowerCase();
  if (key.includes("present")) return "bg-blue-900/30 text-blue-300 border-blue-800/50";
  if (key.includes("app")) return "bg-violet-900/30 text-violet-300 border-violet-800/50";
  if (key.includes("domain")) return "bg-emerald-900/30 text-emerald-300 border-emerald-800/50";
  if (key.includes("infra") || key.includes("data")) return "bg-amber-900/30 text-amber-300 border-amber-800/50";
  if (key.includes("security") || key.includes("auth")) return "bg-rose-900/30 text-rose-300 border-rose-800/50";
  return "bg-slate-800/50 text-slate-300 border-slate-700/60";
}
