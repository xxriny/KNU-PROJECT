import React, { useMemo, useState } from "react";
import useAppStore from "../../store/useAppStore";
import { StatCard, StatusBadge, Section, EmptyState } from "./SharedComponents";
import { toCompactModuleLabel, buildReqFunctionNameMap } from "./resultUtils";
import { Layers, GitBranch, ArrowRight, Shield } from "lucide-react";

function SAArchitectureTab() {
  const { sa_phase5, sa_phase7, activateOutputTab } = useAppStore();
  if (!sa_phase5 && !sa_phase7) {
    return <EmptyState text="아키텍처 결과가 없습니다" />;
  }

  const [selectedLayer, setSelectedLayer] = useState("all");
  const [searchTerm, setSearchTerm] = useState("");

  const layerMeta = {
    presentation: {
      label: "Presentation",
      chip: "bg-blue-600/20 text-blue-300",
      panel: "border-blue-800/40 bg-blue-950/10",
    },
    application: {
      label: "Application",
      chip: "bg-purple-600/20 text-purple-300",
      panel: "border-purple-800/40 bg-purple-950/10",
    },
    domain: {
      label: "Domain",
      chip: "bg-teal-600/20 text-teal-300",
      panel: "border-teal-800/40 bg-teal-950/10",
    },
    infrastructure: {
      label: "Infrastructure",
      chip: "bg-orange-600/20 text-orange-300",
      panel: "border-orange-800/40 bg-orange-950/10",
    },
    security: {
      label: "Security",
      chip: "bg-red-600/20 text-red-300",
      panel: "border-red-800/40 bg-red-950/10",
    },
    unknown: {
      label: "Unclassified",
      chip: "bg-slate-700 text-slate-300",
      panel: "border-slate-700/70 bg-slate-900/40",
    },
  };

  const normalizeLayer = (rawLayer) => {
    const key = String(rawLayer || "").trim().toLowerCase();
    if (!key) return "application";
    if (key.includes("present")) return "presentation";
    if (key.includes("app")) return "application";
    if (key.includes("domain") || key.includes("business")) return "domain";
    if (key.includes("infra") || key.includes("data") || key.includes("storage")) return "infrastructure";
    if (key.includes("security") || key.includes("auth")) return "security";
    if (layerMeta[key]) return key;
    return "unknown";
  };

  const grouped = useMemo(() => {
    const map = {};
    for (const req of sa_phase5?.mapped_requirements || []) {
      const layer = normalizeLayer(req.layer);
      if (!map[layer]) map[layer] = [];
      map[layer].push(req);
    }
    return map;
  }, [sa_phase5?.mapped_requirements]);

  const layerOrder = useMemo(() => {
    const defaults = ["presentation", "application", "domain", "infrastructure", "security"];
    const fromModel = (sa_phase5?.layer_order || []).map((layer) => normalizeLayer(layer));
    const combined = [...fromModel, ...defaults];
    return combined.filter((layer, idx) => combined.indexOf(layer) === idx);
  }, [sa_phase5?.layer_order]);

  const contracts = useMemo(
    () =>
      (sa_phase7?.interface_contracts || []).map((contract) => ({
        ...contract,
        normalizedLayer: normalizeLayer(contract.layer),
      })),
    [sa_phase7?.interface_contracts]
  );

  const filteredContracts = useMemo(() => {
    const q = searchTerm.trim().toLowerCase();
    return contracts.filter((contract) => {
      if (selectedLayer !== "all" && contract.normalizedLayer !== selectedLayer) return false;
      if (!q) return true;
      const haystack = [
        contract.contract_id,
        contract.layer,
        contract.input_spec,
        contract.output_spec,
        contract.req_id,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(q);
    });
  }, [contracts, searchTerm, selectedLayer]);

  const totalMappedRequirements = (sa_phase5?.mapped_requirements || []).length;
  const activeLayerCount = Object.keys(grouped).filter(
    (layer) => (grouped[layer] || []).length > 0
  ).length;
  const guardrailCount = (sa_phase7?.guardrails || []).length;
  const reqFunctionNameMap = useMemo(
    () => buildReqFunctionNameMap(sa_phase5?.mapped_requirements),
    [sa_phase5?.mapped_requirements]
  );
  const toHumanReadableTitle = (contract) => {
    const source = String(contract?.interface_name || contract?.description || "").trim();
    if (source) {
      const normalized = source
        .replace(/^IF[-_]/i, "")
        .replace(/[._-]+/g, " ")
        .replace(/\s+/g, " ")
        .trim();

      const lower = normalized.toLowerCase();

      const phraseRules = [
        { test: /(init|initialize|bootstrap).*(analysis|scan)/, value: "프로젝트 분석 초기화" },
        { test: /(render|display).*(result|output)/, value: "분석 결과 렌더링" },
        { test: /(collect|gather).*(metric|log)/, value: "메트릭 수집" },
        { test: /(update|set).*(state|store|ui)/, value: "상태 업데이트" },
        { test: /(start|create).*(session)/, value: "세션 시작" },
        { test: /(load|fetch|get).*(project|data|result)/, value: "데이터 조회" },
        { test: /(save|persist|write).*(result|state|session)/, value: "결과 저장" },
        { test: /(validate|check).*(input|request|schema)/, value: "입력 검증" },
      ];

      for (const rule of phraseRules) {
        if (rule.test.test(lower)) return rule.value;
      }

      const wordMap = {
        init: "초기화",
        initialize: "초기화",
        analysis: "분석",
        analyze: "분석",
        project: "프로젝트",
        session: "세션",
        result: "결과",
        results: "결과",
        output: "출력",
        input: "입력",
        render: "렌더링",
        update: "업데이트",
        state: "상태",
        fetch: "조회",
        load: "불러오기",
        save: "저장",
        collect: "수집",
        metric: "메트릭",
        metrics: "메트릭",
        log: "로그",
        logs: "로그",
        api: "API",
        event: "이벤트",
        queue: "큐",
        pipeline: "파이프라인",
        context: "컨텍스트",
        contract: "계약",
        module: "모듈",
      };

      const translated = normalized
        .split(" ")
        .map((token) => {
          const key = token.toLowerCase();
          return wordMap[key] || "";
        })
        .filter(Boolean)
        .join(" ")
        .trim();

      if (translated) return translated;
    }
    if (contract?.req_id) return `${contract.req_id} 처리 인터페이스`;
    return "모듈 인터페이스";
  };
  const inferCommType = (contract) => {
    const corpus = [
      contract?.interface_name,
      contract?.input_spec,
      contract?.output_spec,
      contract?.layer,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();

    if (/(api|rest|http|endpoint|request|response|fetch)/.test(corpus)) {
      return { label: "API", tone: "bg-cyan-600/20 text-cyan-300 border-cyan-800/40" };
    }
    if (/(ui|render|view|component|state|store|screen)/.test(corpus)) {
      return { label: "UI", tone: "bg-fuchsia-600/20 text-fuchsia-300 border-fuchsia-800/40" };
    }
    if (/(event|queue|topic|stream|metric|log|emit|publish|subscribe)/.test(corpus)) {
      return { label: "Event", tone: "bg-amber-600/20 text-amber-300 border-amber-800/40" };
    }
    return { label: "Internal", tone: "bg-slate-700/40 text-slate-300 border-slate-700/60" };
  };
  return (
    <div className="h-full overflow-y-auto p-4 space-y-4">
      {sa_phase5 && (
        <Section title="아키텍처 매핑" icon={<Layers size={12} />}>
          <div className="flex items-center gap-2 mb-3 flex-wrap">
            <span className="text-[13px] text-slate-400">패턴</span>
            <span className="px-2 py-0.5 rounded bg-blue-600/20 text-blue-300 text-[13px]">{sa_phase5.pattern || "Clean Architecture"}</span>
            <StatusBadge status={sa_phase5.status || "Needs_Clarification"} />
            <button
              type="button"
              onClick={() => activateOutputTab("sa_system")}
              className="ml-auto text-[12px] px-2 py-1 rounded border border-slate-700 text-slate-300 hover:bg-slate-800"
            >
              시스템 다이어그램 보기
            </button>
            <button
              type="button"
              onClick={() => activateOutputTab("sa_uml")}
              className="text-[12px] px-2 py-1 rounded border border-slate-700 text-slate-300 hover:bg-slate-800"
            >
              UML 보기
            </button>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-4">
            <StatCard label="매핑 요구사항" value={totalMappedRequirements} color="text-blue-300" />
            <StatCard label="활성 레이어" value={activeLayerCount} color="text-teal-300" />
            <StatCard label="인터페이스 계약" value={contracts.length} color="text-purple-300" />
            <StatCard label="가드레일" value={guardrailCount} color="text-red-300" />
          </div>

          <div className="mb-2 text-[13px] text-slate-500">레이어 보드</div>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-2">
            {layerOrder.map((layer) => {
              const reqs = grouped[layer] || [];
              const meta = layerMeta[layer] || layerMeta.unknown;
              const isSelected = selectedLayer === layer;
              return (
                <button
                  type="button"
                  key={layer}
                  onClick={() => setSelectedLayer(isSelected ? "all" : layer)}
                  className={`flex flex-col justify-start items-stretch text-left rounded-lg border p-3 min-h-[156px] align-top transition ${meta.panel} ${isSelected ? "ring-1 ring-slate-400" : "hover:bg-slate-800/40"}`}
                >
                  <div className="w-full self-start space-y-2">
                    <div className="flex items-center justify-between gap-2">
                      <span className={`px-2 py-0.5 rounded text-[12px] font-medium ${meta.chip}`}>{meta.label}</span>
                      <span className="text-[12px] text-slate-500">{reqs.length}개</span>
                    </div>
                    {reqs.length > 0 ? (
                      <div className="space-y-1">
                        {reqs.slice(0, 3).map((req) => (
                          <div key={req.REQ_ID} className="text-[13px] text-slate-300 leading-snug break-words">
                            <span className="text-slate-300">{reqFunctionNameMap[req.REQ_ID] || toCompactModuleLabel(req.description)}</span>
                            <span className="text-slate-500 font-mono ml-1">({req.REQ_ID})</span>
                          </div>
                        ))}
                        {reqs.length > 3 && (
                          <div className="text-[12px] text-slate-500">+{reqs.length - 3}개 더 있음</div>
                        )}
                      </div>
                    ) : (
                      <div className="text-[13px] text-slate-600">매핑된 요구사항 없음</div>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        </Section>
      )}

      {sa_phase7 && (
        <Section title="인터페이스 계약 탐색" icon={<GitBranch size={12} />}>
          <div className="mb-2 flex items-center gap-2 flex-wrap">
            <StatusBadge status={sa_phase7.status || "Needs_Clarification"} />
            <span className="text-[13px] text-slate-500">총 {contracts.length}개 계약</span>
            {selectedLayer !== "all" && (
              <span className="text-[12px] px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                레이어 필터: {(layerMeta[selectedLayer] || layerMeta.unknown).label}
              </span>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-2 mb-3">
            <input
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="계약 ID, 입력/출력, REQ_ID 검색"
              className="md:col-span-2 bg-slate-900 border border-slate-700 rounded px-2 py-1.5 text-[13px] text-slate-200 placeholder:text-slate-500"
            />
            <select
              value={selectedLayer}
              onChange={(e) => setSelectedLayer(e.target.value)}
              className="bg-slate-900 border border-slate-700 rounded px-2 py-1.5 text-[13px] text-slate-200"
            >
              <option value="all">전체 레이어</option>
              {layerOrder.map((layer) => (
                <option key={layer} value={layer}>
                  {(layerMeta[layer] || layerMeta.unknown).label}
                </option>
              ))}
              <option value="unknown">Unclassified</option>
            </select>
          </div>

          {(sa_phase7.guardrails || []).length > 0 && (
            <div className="mb-3">
              <div className="text-[12px] text-slate-500 mb-1.5 uppercase tracking-wider">Guardrails</div>
              <ul className="space-y-1">
                {sa_phase7.guardrails.map((g, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-[13px] text-slate-400">
                    <Shield size={10} className="text-red-400 mt-0.5 flex-shrink-0" />
                    {g}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {filteredContracts.length > 0 ? (
            <div className="space-y-2">
              {filteredContracts.slice(0, 40).map((c, idx) => {
                const commType = inferCommType(c);
                const title = toHumanReadableTitle(c);
                const reqLabel = reqFunctionNameMap[c.req_id] || c.req_id || c.contract_id || `ROW-${idx + 1}`;
                const layerLabel = (layerMeta[c.normalizedLayer] || layerMeta.unknown).label;
                return (
                  <div key={idx} className="rounded-lg border border-slate-700/70 bg-slate-900/40 p-3">
                    <div className="flex items-start gap-2 mb-2 flex-wrap">
                      <span className={`px-2 py-0.5 rounded border text-[12px] font-medium ${commType.tone}`}>
                        {commType.label}
                      </span>
                      <h5 className="text-[15px] font-semibold text-slate-200 leading-tight">
                        {title} <span className="text-slate-400">({reqLabel})</span>
                      </h5>
                      <span className={`ml-auto px-1.5 py-0.5 rounded text-[12px] ${(layerMeta[c.normalizedLayer] || layerMeta.unknown).chip}`}>
                        {layerLabel}
                      </span>
                    </div>

                    <div className="text-[12px] text-slate-500 mb-2">
                      원본 ID: {c.contract_id || "NO-ID"}
                      <span className={`ml-2 ${c.req_id ? "text-slate-500" : "text-slate-700"}`}>REQ: {c.req_id || "-"}</span>
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-[1fr_auto_1fr] gap-2 items-center">
                      <div className="rounded border border-slate-700 bg-slate-800/60 p-2">
                        <div className="text-[11px] uppercase tracking-wider text-slate-500 mb-1">Input</div>
                        <div className={`font-mono text-[12px] leading-relaxed break-words ${c.input_spec ? "text-slate-200" : "text-slate-600"}`}>
                          {c.input_spec || "-"}
                        </div>
                      </div>

                      <div className="flex justify-center text-slate-500">
                        <ArrowRight size={14} />
                      </div>

                      <div className="rounded border border-slate-700 bg-slate-800/60 p-2">
                        <div className="text-[11px] uppercase tracking-wider text-slate-500 mb-1">Output</div>
                        <div className={`font-mono text-[12px] leading-relaxed break-words ${c.output_spec ? "text-slate-200" : "text-slate-600"}`}>
                          {c.output_spec || "-"}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}

              {filteredContracts.length > 40 && (
                <p className="text-[12px] text-slate-600 text-right">+{filteredContracts.length - 40}개 더 있음</p>
              )}
            </div>
          ) : (
            <div className="text-[13px] text-slate-500 border border-slate-800 rounded p-3">
              현재 필터 조건에 맞는 인터페이스 계약이 없습니다.
            </div>
          )}
        </Section>
      )}
    </div>
  );
}

export default SAArchitectureTab;
