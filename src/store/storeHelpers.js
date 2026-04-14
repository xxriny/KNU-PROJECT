/**
 * Store 헬퍼 — useAppStore에서 추출된 순수 함수들
 */

export const SESSION_STORAGE_KEY = "pm_sessions";
export const DEFAULT_VIEWPORT_TAB = { kind: "output", id: "home" };

export const MODE_TO_ACTION_TYPE = {
  create: "CREATE",
  update: "UPDATE",
  reverse: "REVERSE_ENGINEER",
};

export const MODE_TO_PIPELINE_TYPE = {
  create: "analysis_create",
  update: "analysis_update",
  reverse: "analysis_reverse",
};

export function normalizeMode(mode) {
  return MODE_TO_ACTION_TYPE[mode] ? mode : "create";
}

export function loadSessions() {
  try {
    return JSON.parse(localStorage.getItem(SESSION_STORAGE_KEY) || "[]");
  } catch {
    return [];
  }
}

export function persistSessions(sessions) {
  try {
    localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(sessions));
  } catch {
    // Non-fatal localStorage failure.
  }
}

export function cloneViewportTab(tab) {
  return tab ? { kind: tab.kind, id: tab.id } : { ...DEFAULT_VIEWPORT_TAB };
}

export function normalizeOutputTabId(tabId) {
  if (tabId === "sa_overview" || tabId === "sa_feasibility") {
    return "overview";
  }
  if (tabId === "topology") {
    return "context";
  }
  return tabId;
}

export function extractRunId(value) {
  if (typeof value !== "string") {
    return null;
  }
  const match = value.match(/(\d{8}_\d{6})/);
  return match ? match[1] : null;
}

export function inferPipelineTypeFromResult(data) {
  const hinted = data?.pipeline_type;
  if (typeof hinted === "string" && hinted) {
    return hinted;
  }
  const actionType = (data?.metadata?.action_type || "").toUpperCase();
  if (actionType === "REVERSE_ENGINEER") {
    return "analysis_reverse";
  }
  if (actionType === "UPDATE") {
    return "analysis_update";
  }
  return "analysis_create";
}

/** SA 관련 결과 필드의 초기값 (startAnalysis, resetPipeline, loadSession에서 공유) */
export const EMPTY_RESULT_FIELDS = {
  resultData: null,
  requirements_rtm: [],
  semantic_graph: null,
  context_spec: null,
  sa_reverse_context: null,
  sa_output: null,
  sa_artifacts: null,
  system_scan: null,
  sa_phase2: null,
  sa_phase3: null,
  sa_phase4: null,
  sa_phase5: null,
  sa_phase6: null,
  sa_phase7: null,
  sa_phase8: null,
  pm_bundle: null,
  pm_coverage_rate: 0,
  pm_warnings: [],
  metadata: null,
};

import useAppStore from "./useAppStore";

/** 배열 타입 검증 및 디버깅 로그 기록 */
function validateArray(key, data, fallback = []) {
  if (Array.isArray(data)) return data;
  if (!data && data !== "") return fallback;

  // 타입 불일치 발생 시 디버그 로그 기록
  const actualType = typeof data;
  const message = `[TypeMismatch] '${key}' expected Array, but got ${actualType}`;
  
  // Zustand store의 getState를 통해 직접 액션 호출
  if (useAppStore.getState().addDebugLog) {
    useAppStore.getState().addDebugLog({
      level: "error",
      key,
      message,
      rawData: data
    });
  }
  
  // 문자열인데 내용이 있는 경우 등 상황에 따라 래핑 혹은 빈 배열 반환
  if (typeof data === "string" && data.length > 0) return [data];
  return fallback;
}

/** resultData에서 개별 필드를 추출하는 공통 로직 */
export function spreadResultData(data) {
  const pmBundle = data?.pm_bundle || null;
  
  // 검증 유틸リティ를 통한 안전한 데이터 추출
  const rtm = validateArray("requirements_rtm", pmBundle?.data?.rtm || data?.requirements_rtm || data?.raw_requirements);
  const techStacks = validateArray("tech_stacks", pmBundle?.data?.tech_stacks || data?.stack_planner_output?.stack_mapping);
  const pmWarnings = validateArray("pm_warnings", data?.pm_warnings);
  const thinkingLog = validateArray("thinking_log", data?.thinking_log);

  return {
    resultData: data || null,
    pm_bundle: pmBundle,
    pm_coverage_rate: data?.pm_coverage_rate || 0,
    pm_warnings: pmWarnings,
    requirements_rtm: rtm,
    tech_stacks: techStacks,
    metadata: data?.metadata || null,
    semantic_graph: data?.semantic_graph || null,
    context_spec: data?.context_spec || null,
    sa_reverse_context: data?.sa_reverse_context || null,
    sa_output: data?.sa_output || null,
    sa_artifacts: data?.sa_artifacts || null,
    system_scan: data?.system_scan || null,
    sa_phase2: data?.sa_phase2 || null,
    sa_phase3: data?.sa_phase3 || null,
    sa_phase4: data?.sa_phase4 || null,
    sa_phase5: data?.sa_phase5 || null,
    sa_phase6: data?.sa_phase6 || null,
    sa_phase7: data?.sa_phase7 || null,
    sa_phase8: data?.sa_phase8 || null,
    thinking_log: thinkingLog,
  };
}
