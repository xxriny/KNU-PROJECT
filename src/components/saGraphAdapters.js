import { LAYER_ORDER, LAYER_COLOR, getLayerX, buildDynamicLayerXMap } from "./graphLayout";
import { groupBy, dedupeEdges, compactPathLabel, buildDegreeMap } from "./graphUtils";

export function normalizeSystemDiagramForGraph(spec) {
  const nodes = spec?.nodes || [];
  const edges = spec?.edges || [];
  const layerOrder = spec?.layer_order || LAYER_ORDER;
  const degreeMap = buildDegreeMap(edges);
  const byLayer = groupBy(nodes, (node) => node.layer || "Unknown");
  const { xMap } = buildDynamicLayerXMap(byLayer, layerOrder, { minGap: 330, maxGap: 560, gapBias: -20 });

  const graphNodes = [];
  for (const [layer, layerNodes] of Object.entries(byLayer)) {
    const x = xMap[layer] ?? getLayerX(layer, layerOrder);
    const sortedLayerNodes = [...layerNodes].sort((a, b) => {
      const degreeDiff = (degreeMap[b.id] || 0) - (degreeMap[a.id] || 0);
      if (degreeDiff !== 0) return degreeDiff;
      return String(a.id).localeCompare(String(b.id));
    });

    sortedLayerNodes.forEach((node, index) => {
      graphNodes.push({
        id: node.id,
        position: { x, y: 84 + index * 132 },
        sourcePosition: "right",
        targetPosition: "left",
        data: {
          title: node.label || node.id,
          subtitle: compactPathLabel(node.file_path || node.label || node.id),
          badge: layer,
          accent: LAYER_COLOR[layer] || LAYER_COLOR.Unknown,
          detail: {
            layer,
            layer_confidence: node.layer_confidence,
            full_label: node.label || node.id,
            module_id: node.id,
            file_path: node.file_path || "-",
            canonical_id: node.canonical_id || node.id,
            source_kind: node.source_kind || "code_scan",
            depends_on: node.depends_on || [],
            mapping_reason: node.mapping_reason || "",
            layer_evidence: node.layer_evidence || [],
            degree: degreeMap[node.id] || 0,
          },
        },
      });
    });
  }

  const graphEdges = dedupeEdges(
    edges.map((edge, index) => {
      const relationType = edge.type || "data_flow";
      const confidence = typeof edge.confidence === "number" ? edge.confidence : null;
      const confidenceTag = confidence !== null ? ` (${Math.round(confidence * 100)}%)` : "";
      const color = relationType === "explicit"
        ? "#60a5fa"
        : relationType === "semantic"
        ? "#a78bfa"
        : relationType === "execution_order"
        ? "#334155"
        : "#475569";
      return {
        id: `sys-${index}-${edge.source}-${edge.target}`,
        source: edge.source,
        target: edge.target,
        type: "smoothstep",
        animated: relationType === "data_flow" || relationType === "execution_order",
        label: `${relationType}${confidenceTag}`,
        style: {
          stroke: color,
          strokeWidth: edge.canonical ? 2.3 : relationType === "execution_order" ? 1.1 : 1.7,
          strokeDasharray: relationType === "execution_order" ? "5 5" : relationType === "data_flow" ? "7 5" : undefined,
        },
        data: {
          relationType,
          confidence,
          tokens: edge.tokens || [],
        },
      };
    })
  );

  return {
    nodes: graphNodes,
    edges: graphEdges,
    legend: [
      { label: "Presentation", color: LAYER_COLOR.Presentation },
      { label: "Application", color: LAYER_COLOR.Application },
      { label: "Domain", color: LAYER_COLOR.Domain },
      { label: "Infrastructure", color: LAYER_COLOR.Infrastructure },
      { label: "Security", color: LAYER_COLOR.Security },
    ],
  };
}

export function normalizeFlowchartForGraph(spec) {
  const stages = spec?.stages || [];
  const graphNodes = [];
  const graphEdges = [];

  stages.forEach((stage, index) => {
    const stageId = `stage-${stage.stage || index + 1}`;
    const functionNames = (stage.function_names || []).filter(Boolean);
    const reqIds = stage.req_ids || [];
    const previewList = functionNames.length > 0 ? functionNames : reqIds;
    const first = String(previewList[0] || "").trim();
    const firstCompact = first.length > 14 ? `${first.slice(0, 14)}...` : first;
    const remaining = Math.max(previewList.length - 1, 0);
    graphNodes.push({
      id: stageId,
      position: { x: 120 + index * 300, y: 80 },
      sourcePosition: "right",
      targetPosition: "left",
      data: {
        title: `Stage ${stage.stage || index + 1}`,
        subtitle: firstCompact ? `${firstCompact}${remaining > 0 ? ` 외 ${remaining}개` : ""}` : "-",
        badge: stage.kind || "sequential",
        accent: stage.kind === "parallel" ? "#14b8a6" : "#3b82f6",
        detail: {
          function_names: functionNames,
          req_ids: reqIds,
          kind: stage.kind || "sequential",
        },
      },
    });

    if (index > 0) {
      const prevId = `stage-${stages[index - 1].stage || index}`;
      graphEdges.push({
        id: `flow-${prevId}-${stageId}`,
        source: prevId,
        target: stageId,
        type: "smoothstep",
        style: { stroke: "#64748b", strokeWidth: 2 },
      });
    }
  });

  return {
    nodes: graphNodes,
    edges: graphEdges,
    legend: [
      { label: "Sequential", color: "#3b82f6" },
      { label: "Parallel", color: "#14b8a6" },
    ],
  };
}

export function normalizeUMLForGraph(spec, options = {}) {
  const components = spec?.components || [];
  const providedInterfaces = spec?.provided_interfaces || [];
  const relations = spec?.relations || [];

  const mode = options.mode || "detail"; // detail | cluster
  const layerFilter = String(options.layerFilter || "").trim();
  const hideExecutionOrder = options.hideExecutionOrder !== false;
  const minConfidence = typeof options.minConfidence === "number" ? options.minConfidence : 0;
  const showEdgeLabels = options.showEdgeLabels !== false;

  const filteredComponents = layerFilter
    ? components.filter((item) => (item.layer || "Unknown") === layerFilter)
    : components;
  const componentIdSet = new Set(filteredComponents.map((item) => item.id));
  const filteredRelations = relations.filter((relation) => {
    if (!componentIdSet.has(relation.source) || !componentIdSet.has(relation.target)) return false;
    if (hideExecutionOrder && relation.relation_type === "execution_order") return false;
    if (typeof relation.confidence === "number" && relation.confidence < minConfidence) return false;
    return true;
  });

  if (mode === "cluster") {
    const componentById = new Map(components.map((item) => [item.id, item]));
    const byLayer = groupBy(components, (component) => component.layer || "Unknown");
    const orderedLayers = LAYER_ORDER.filter((layer) => (byLayer[layer] || []).length > 0);
    const fallbackLayers = Object.keys(byLayer).filter((layer) => !orderedLayers.includes(layer));
    const layers = [...orderedLayers, ...fallbackLayers];

    const graphNodes = layers.map((layer, index) => {
      const layerItems = byLayer[layer] || [];
      const interfaceCount = providedInterfaces.filter((itf) => {
        const comp = componentById.get(itf.component_id);
        return comp && (comp.layer || "Unknown") === layer;
      }).length;
      return {
        id: `cluster-${layer}`,
        position: { x: 120 + index * 340, y: 140 },
        sourcePosition: "right",
        targetPosition: "left",
        data: {
          title: layer,
          subtitle: `${layerItems.length} components`,
          badge: `IF ${interfaceCount}`,
          accent: LAYER_COLOR[layer] || LAYER_COLOR.Unknown,
          detail: {
            layer,
            description: `${layer} 레이어 집계 노드`,
            mapped_requirements: layerItems.map((item) => item.id),
          },
        },
      };
    });

    const edgeMap = new Map();
    filteredRelations.forEach((relation) => {
      const srcLayer = componentById.get(relation.source)?.layer || "Unknown";
      const dstLayer = componentById.get(relation.target)?.layer || "Unknown";
      const relationType = relation.relation_type || relation.relation || "depends_on";
      const key = `${srcLayer}|${dstLayer}|${relationType}`;
      const prev = edgeMap.get(key) || { count: 0, canonical: false };
      edgeMap.set(key, {
        count: prev.count + 1,
        canonical: prev.canonical || Boolean(relation.canonical),
        relationType,
        source: `cluster-${srcLayer}`,
        target: `cluster-${dstLayer}`,
      });
    });

    const graphEdges = [...edgeMap.values()].map((entry, index) => ({
      id: `uml-cluster-${index}-${entry.source}-${entry.target}`,
      source: entry.source,
      target: entry.target,
      type: "smoothstep",
      label: `${entry.relationType} · ${entry.count}`,
      style: {
        stroke: entry.canonical ? "#22c55e" : "#64748b",
        strokeWidth: Math.min(4, 1.2 + entry.count * 0.08),
      },
    }));

    return {
      nodes: graphNodes,
      edges: dedupeEdges(graphEdges),
      legend: [
        { label: "Layer Cluster", color: "#22c55e" },
        { label: "Aggregated Relation", color: "#64748b" },
      ],
    };
  }

  const graphNodes = [];
  const graphEdges = [];

  const byLayer = groupBy(filteredComponents, (component) => component.layer || "Unknown");
  const orderedLayers = LAYER_ORDER.filter((layer) => (byLayer[layer] || []).length > 0);
  const fallbackLayers = Object.keys(byLayer).filter((layer) => !orderedLayers.includes(layer));
  const layers = [...orderedLayers, ...fallbackLayers];

  layers.forEach((layer, layerIndex) => {
    const layerItems = byLayer[layer] || [];
    layerItems.forEach((item, index) => {
      const interfaceCount = providedInterfaces.filter((itf) => itf.component_id === item.id).length;
      const position = {
        x: 140 + index * 250,
        y: 90 + layerIndex * 210,
      };
      graphNodes.push({
        id: item.id,
        position,
        sourcePosition: "right",
        targetPosition: "left",
        data: {
          title: item.name || item.id,
          subtitle: item.description || "",
          badge: `${layer} · IF ${interfaceCount}`,
          accent: LAYER_COLOR[layer] || LAYER_COLOR.Unknown,
          detail: {
            layer,
            interfaces: providedInterfaces.filter((itf) => itf.component_id === item.id),
          },
        },
      });
    });
  });

  filteredRelations.forEach((relation, index) => {
    graphEdges.push({
      id: `uml-${index}-${relation.source}-${relation.target}`,
      source: relation.source,
      target: relation.target,
      type: "smoothstep",
      label: showEdgeLabels ? relation.relation_type || relation.relation || "depends_on" : "",
      style: { stroke: relation.canonical ? "#22c55e" : "#64748b", strokeWidth: relation.canonical ? 2.2 : 1.6 },
    });
  });

  return {
    nodes: graphNodes,
    edges: dedupeEdges(graphEdges),
    legend: [
      { label: "Canonical", color: "#22c55e" },
      { label: "Inferred", color: "#64748b" },
    ],
  };
}

const CONTAINER_LAYER_ORDER = ["Presentation", "Application", "Domain", "Infrastructure", "External"];

const CONTAINER_EDGE_COLOR = {
  http: "#3b82f6",
  ipc: "#8b5cf6",
  internal: "#475569",
  data: "#14b8a6",
  external: "#f59e0b",
  process: "#6366f1",
};

export function normalizeContainerDiagramForGraph(spec) {
  const components = spec?.components || [];
  const externalSystems = spec?.external_systems || [];
  const connections = spec?.connections || [];

  const allNodes = [...components, ...externalSystems];
  const byLayer = groupBy(allNodes, (n) => n.layer || "Unknown");
  const { xMap } = buildDynamicLayerXMap(byLayer, CONTAINER_LAYER_ORDER, { minGap: 360, maxGap: 620, gapBias: -10 });

  const graphNodes = [];
  for (const [layer, layerNodes] of Object.entries(byLayer)) {
    const x = xMap[layer] ?? xMap.Infrastructure ?? 120;
    layerNodes.forEach((node, index) => {
      const isExternal = node.node_kind === "external";
      const accent = isExternal ? "#f59e0b" : (LAYER_COLOR[layer] || LAYER_COLOR.Unknown);
      const badge = isExternal ? "External" : `${node.file_count ?? 0} files`;
      graphNodes.push({
        id: node.id,
        position: { x, y: 80 + index * 210 },
        sourcePosition: "right",
        targetPosition: "left",
        data: {
          title: node.label || node.id,
          subtitle: node.description || "",
          badge,
          accent,
          detail: {
            layer: node.layer,
            node_kind: node.node_kind,
            file_count: node.file_count,
            description: node.description,
            files: node.files || [],
            mapped_requirements: node.mapped_requirements || [],
          },
        },
      });
    });
  }

  const graphEdges = dedupeEdges(
    connections.map((conn, index) => {
      const color = CONTAINER_EDGE_COLOR[conn.edge_type] || "#475569";
      const isExternal = conn.edge_type === "external";
      return {
        id: `ctn-${index}-${conn.source}-${conn.target}`,
        source: conn.source,
        target: conn.target,
        type: "smoothstep",
        animated: isExternal,
        label: conn.protocol || conn.edge_type,
        style: {
          stroke: color,
          strokeWidth: isExternal ? 1.5 : 2,
          strokeDasharray: isExternal ? "5 4" : undefined,
        },
        data: { edge_type: conn.edge_type, protocol: conn.protocol },
      };
    })
  );

  return {
    nodes: graphNodes,
    edges: graphEdges,
    legend: [
      { label: "Presentation", color: LAYER_COLOR.Presentation },
      { label: "Application", color: LAYER_COLOR.Application },
      { label: "Domain", color: LAYER_COLOR.Domain },
      { label: "Infrastructure", color: LAYER_COLOR.Infrastructure },
      { label: "External", color: "#f59e0b" },
    ],
  };
}
