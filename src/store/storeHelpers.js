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
  tables: null,
  apis: null,
  tech_stacks: [],
  sa_advisor_output: null,
  metadata: null,
};

/** 배열 타입 검증 및 디버깅 로그 기록 */
function validateArray(key, data, fallback = []) {
  if (Array.isArray(data)) return data;
  if (!data && data !== "") return fallback;

  // 타입 불일치 발생 시 콘솔에 기록 (순환 참조 방지를 위해 store 직접 접근 지양)
  console.warn(`[TypeMismatch] '${key}' expected Array, but got ${typeof data}`, data);

  if (typeof data === "string" && data.length > 0) return [data];
  return fallback;
}

/** resultData에서 개별 필드를 추출하는 공통 로직 (LLM Shaper 최적화) */
export function spreadResultData(data) {
  if (!data) return EMPTY_RESULT_FIELDS;

  // 1. LLM Shaper가 생성한 표준 필드들 (최우선)
  const rtm = validateArray("requirements_rtm", data.requirements_rtm || []);
  const techStacks = validateArray("tech_stacks", data.tech_stacks || []);
  const apis = validateArray("apis", data.apis || []);
  const tables = validateArray("tables", data.tables || []);
  const components = validateArray("components", data.components || []);
  const recommendations = validateArray("recommendations", data.recommendations || []);
  
  // 2. 과거 데이터 또는 내부 번들에서 추출 (폴백)
  const pmBundle = data.pm_bundle || {};
  const pmData = pmBundle.data || {};

  return {
    resultData: data,
    metadata: data.metadata || {
      project_name: data.project_name,
      status: data.status,
      run_id: data.run_id,
      action_type: data.action_type
    },
    project_overview: data.project_overview || {
      project_name: data.project_name,
      summary: data.summary,
      status: data.status
    },
    // 핵심 리스트 데이터
    requirements_rtm: rtm.length > 0 ? rtm : validateArray("rtm_fallback", pmData.rtm),
    tech_stacks: techStacks.length > 0 ? techStacks : validateArray("stack_fallback", pmData.stacks),
    apis: apis,
    tables: tables,
    components: components,
    recommendations: recommendations,
    
    // 지표 및 요약
    pm_coverage_rate: data.pm_coverage_rate || pmData.coverage_rate || 0,
    pm_warnings: validateArray("pm_warnings", data.pm_warnings || pmData.warnings),
    metrics: data.metrics || { performance: 0, stability: 0, integrity: "UNKNOWN" },
    analysis: {
      summary: data.summary || "분석 결과를 표시할 수 없습니다.",
      source: "llm_shaper"
    },
    
    // 시스템 필드
    thinking_log: validateArray("thinking_log", data.thinking_log),
    sa_output: data.sa_output || data, // 탭 활성화 호환성
    sa_artifacts: data.sa_artifacts || null,
  };
}
