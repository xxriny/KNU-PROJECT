/**
 * 그래프 레이아웃 유틸리티 — 레이어 기반 x축 배치, 동적 갭 계산
 */

export const LAYER_ORDER = ["Presentation", "Application", "Domain", "Infrastructure", "Security", "Unknown"];

export const LAYER_COLOR = {
  Presentation: "#3b82f6",
  Application: "#8b5cf6",
  Domain: "#14b8a6",
  Infrastructure: "#f59e0b",
  Security: "#ef4444",
  Unknown: "#64748b",
};

export function getLayerX(layer, customOrder = []) {
  const order = customOrder.length > 0 ? customOrder : LAYER_ORDER;
  const index = order.indexOf(layer);
  const lane = index >= 0 ? index : order.indexOf("Unknown");
  return 120 + lane * 620;
}

export function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

export function buildDynamicLayerXMap(grouped, order = LAYER_ORDER, options = {}) {
  const activeLayers = order.filter((layer) => (grouped[layer] || []).length > 0);
  const resolvedLayers = activeLayers.length > 0 ? activeLayers : order;
  const laneCount = resolvedLayers.length;
  const maxLaneSize = Math.max(1, ...resolvedLayers.map((layer) => (grouped[layer] || []).length || 0));
  const baseX = options.baseX ?? 120;
  const minGap = options.minGap ?? 320;
  const maxGap = options.maxGap ?? 620;
  const gapBias = options.gapBias ?? 0;
  const gap = clamp(maxGap - (laneCount - 1) * 55 - (maxLaneSize - 1) * 18 + gapBias, minGap, maxGap);

  const xMap = {};
  resolvedLayers.forEach((layer, index) => {
    xMap[layer] = baseX + index * gap;
  });
  return { xMap, resolvedLayers, gap };
}
