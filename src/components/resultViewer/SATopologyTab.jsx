import React, { useMemo, useState } from "react";
import useAppStore from "../../store/useAppStore";
import { StatCard, StatusBadge, Section, EmptyState } from "./SharedComponents";
import { AlertTriangle, GitBranch } from "lucide-react";

function SATopologyTab() {
  const { sa_phase5, sa_phase8 } = useAppStore();
  if (!sa_phase8) {
    return <EmptyState text="위상 정렬 결과가 없습니다" />;
  }

  const [selectedCycle, setSelectedCycle] = useState("");
  const queue = sa_phase8.topo_queue || [];
  const cycles = sa_phase8.cyclic_requirements || [];
  const batches = sa_phase8.parallel_batches || [];
  const dependencySources = sa_phase8.dependency_sources || {};

  const reqMeta = useMemo(() => {
    const map = {};
    for (const item of sa_phase5?.mapped_requirements || []) {
      const reqId = item?.REQ_ID || item?.req_id;
      if (!reqId) continue;
      const description = String(item?.description || "")
        .replace(/^핵심\s*분석\s*모듈\s*:\s*/i, "")
        .replace(/^핵심\s*모듈\s*:\s*/i, "")
        .replace(/^분석\s*모듈\s*:\s*/i, "")
        .trim();
      map[reqId] = {
        name: description || "모듈 기능",
        layer: item?.layer || "unknown",
      };
    }
    return map;
  }, [sa_phase5?.mapped_requirements]);

  const orderIndex = useMemo(() => {
    const map = {};
    queue.forEach((rid, idx) => {
      map[rid] = idx + 1;
    });
    return map;
  }, [queue]);

  const layerLabel = (layer) => {
    const key = String(layer || "").toLowerCase();
    if (key.includes("present")) return "Presentation";
    if (key.includes("app")) return "Application";
    if (key.includes("domain") || key.includes("business")) return "Domain";
    if (key.includes("infra") || key.includes("data")) return "Infrastructure";
    if (key.includes("security") || key.includes("auth")) return "Security";
    return "Unknown";
  };

  const layerTone = (layer) => {
    const key = String(layer || "").toLowerCase();
    if (key.includes("present")) return "bg-blue-600/20 text-blue-300";
    if (key.includes("app")) return "bg-purple-600/20 text-purple-300";
    if (key.includes("domain") || key.includes("business")) return "bg-teal-600/20 text-teal-300";
    if (key.includes("infra") || key.includes("data")) return "bg-orange-600/20 text-orange-300";
    if (key.includes("security") || key.includes("auth")) return "bg-red-600/20 text-red-300";
    return "bg-slate-700 text-slate-300";
  };

  const cyclePathMap = useMemo(() => {
    const cyclicSet = new Set(cycles);
    const adjacency = {};
    Object.keys(dependencySources).forEach((target) => {
      const deps = (dependencySources[target] || [])
        .map((src) => src?.from)
        .filter((from) => from && cyclicSet.has(from));
      adjacency[target] = [...new Set(deps)];
    });

    const findPath = (start) => {
      const stack = [[start, [start]]];
      while (stack.length > 0) {
        const [node, path] = stack.pop();
        const nexts = adjacency[node] || [];
        for (const next of nexts) {
          if (next === start && path.length > 1) {
            return [...path, start];
          }
          if (!path.includes(next) && path.length < 8) {
            stack.push([next, [...path, next]]);
          }
        }
      }
      return [];
    };

    const map = {};
    cycles.forEach((rid) => {
      const path = findPath(rid);
      map[rid] = path.length > 0 ? path.join(" ➔ ") : "경로 정보 없음";
    });
    return map;
  }, [cycles, dependencySources]);

  const phaseGroups = useMemo(() => {
    if (batches.length > 0) {
      return batches.map((batch, idx) => ({
        phaseNo: idx + 1,
        title: idx === 0 ? "종속성 없음 (독립 개발 가능)" : `Phase ${idx} 의존`,
        items: batch,
      }));
    }
    if (queue.length === 0) return [];
    return [
      {
        phaseNo: 1,
        title: "순차 실행",
        items: queue,
      },
    ];
  }, [batches, queue]);

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4">
      {/* 상태 요약 */}
      <div className="bg-slate-900/50 rounded-lg p-3 border border-slate-700/50 flex items-center gap-3">
        <StatusBadge status={sa_phase8.status || "Needs_Clarification"} />
        <span className="text-[12px] text-slate-500">
          실행 순서 {queue.length}개
          {cycles.length > 0 && ` · 순환 의존성 ${cycles.length}개`}
        </span>
      </div>

      {/* 순환 의존성 경고 */}
      {cycles.length > 0 && (
        <Section title="순환 의존성 경고" icon={<AlertTriangle size={12} />}>
          <div className="flex flex-wrap gap-2">
            {cycles.map((rid) => (
              <button
                key={rid}
                type="button"
                title={cyclePathMap[rid] || "경로 정보 없음"}
                onClick={() => setSelectedCycle((prev) => (prev === rid ? "" : rid))}
                className="px-2 py-0.5 rounded bg-red-600/20 text-red-300 text-[12px] border border-red-800/30 hover:bg-red-600/30"
              >
                {rid}
              </button>
            ))}
          </div>
          {selectedCycle && (
            <div className="mt-2 rounded border border-red-900/40 bg-red-950/20 p-2 text-[12px] text-red-200">
              {cyclePathMap[selectedCycle] || "경로 정보 없음"}
            </div>
          )}
          <p className="text-[11px] text-slate-600 mt-2">
            순환 의존성이 있는 요구사항은 위상 정렬에서 제외됩니다. 의존성을 재검토하세요.
          </p>
        </Section>
      )}

      {/* 실행 그룹 (Phase) */}
      {phaseGroups.length > 0 && (
        <Section title="실행 그룹 (Topology Queue)" icon={<GitBranch size={12} />}>
          <div className="space-y-3">
            {phaseGroups.map((group) => (
              <div key={group.phaseNo} className="rounded-lg border border-slate-700/70 bg-slate-900/30 p-3">
                <div className="flex items-center gap-2 mb-2 flex-wrap">
                  <span className="px-2 py-0.5 rounded bg-blue-600/20 text-blue-300 text-[12px]">Phase {group.phaseNo}</span>
                  <span className="text-[12px] text-slate-500">{group.title}</span>
                  <span className="ml-auto text-[11px] text-slate-600">{group.items.length}개 모듈</span>
                </div>

                <div className="space-y-1.5">
                  {group.items.map((rid) => {
                    const meta = reqMeta[rid] || { name: "모듈 기능", layer: "unknown" };
                    const seq = orderIndex[rid] || "-";
                    return (
                      <div key={`${group.phaseNo}-${rid}`} className="flex items-center gap-2">
                        <span className="text-[11px] font-mono text-slate-600 w-8 text-right flex-shrink-0">{seq}</span>
                        <span className="text-[12px] text-blue-300 font-mono flex-shrink-0">{rid}</span>
                        <span className="text-[13px] text-slate-200 truncate">{meta.name}</span>
                        <span className={`ml-auto px-1.5 py-0.5 rounded text-[11px] ${layerTone(meta.layer)}`}>
                          {layerLabel(meta.layer)}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}
    </div>
  );
}

export default SATopologyTab;
