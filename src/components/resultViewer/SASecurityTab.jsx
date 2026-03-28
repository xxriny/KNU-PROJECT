import React from "react";
import useAppStore from "../../store/useAppStore";
import { StatCard, StatusBadge, Section, EmptyState } from "./SharedComponents";
import { Shield } from "lucide-react";

function SASecurityTab() {
  const { sa_phase5, sa_phase6, sa_phase7 } = useAppStore();
  if (!sa_phase6) {
    return <EmptyState text="보안 경계 결과가 없습니다" />;
  }

  const toCompactModuleLabel = (text) => {
    const raw = String(text || "").trim();
    if (!raw) return "기능명 없음";
    return raw
      .replace(/^핵심\s*분석\s*모듈\s*:\s*/i, "")
      .replace(/^핵심\s*모듈\s*:\s*/i, "")
      .replace(/^분석\s*모듈\s*:\s*/i, "");
  };

  const extractFileRoot = (...texts) => {
    const joined = texts.filter(Boolean).join(" ").replace(/\\/g, "/");
    const match = joined.match(/((?:src|backend|electron|pipeline|components|store)\/[A-Za-z0-9_./-]+\.[A-Za-z0-9]+)/i);
    return match ? match[1] : "-";
  };

  const toKoreanFunctionName = (rawName) => {
    const normalized = String(rawName || "")
      .replace(/^IF[-_]/i, "")
      .replace(/[._-]+/g, " ")
      .replace(/\s+/g, " ")
      .trim();
    const lower = normalized.toLowerCase();

    const rules = [
      { test: /(init|initialize|bootstrap).*(analysis|scan)/, value: "프로젝트 분석 초기화" },
      { test: /(render|display).*(result|output)/, value: "분석 결과 렌더링" },
      { test: /(collect|gather).*(metric|log)/, value: "메트릭 수집" },
      { test: /(update|set).*(state|store|ui)/, value: "상태 업데이트" },
      { test: /(start|create).*(session)/, value: "세션 시작" },
      { test: /(load|fetch|get).*(project|data|result)/, value: "데이터 조회" },
      { test: /(save|persist|write).*(result|state|session)/, value: "결과 저장" },
      { test: /(validate|check).*(input|request|schema)/, value: "입력 검증" },
    ];
    for (const rule of rules) {
      if (rule.test.test(lower)) return rule.value;
    }
    return normalized || "모듈 기능";
  };

  const isLikelyFilePath = (text) => {
    const value = String(text || "").trim();
    if (!value) return false;
    if (/^(src|backend|electron|pipeline|components|store)\//i.test(value.replace(/\\/g, "/"))) return true;
    if (/[A-Za-z0-9_./-]+\.[A-Za-z0-9]+/.test(value) && /[\\/]/.test(value)) return true;
    return false;
  };

  const reqTitleMap = {};
  const reqFileRootMap = {};
  for (const contract of sa_phase7?.interface_contracts || []) {
    const reqId = contract?.req_id || contract?.REQ_ID;
    if (!reqId || reqId === "-") continue;
    const titleCandidate = toKoreanFunctionName(contract?.interface_name || contract?.contract_id);
    if (titleCandidate && titleCandidate !== "모듈 기능") {
      reqTitleMap[reqId] = titleCandidate;
    }
    if (!reqFileRootMap[reqId] || reqFileRootMap[reqId] === "-") {
      reqFileRootMap[reqId] = extractFileRoot(contract?.input_spec, contract?.output_spec);
    }
  }

  for (const req of sa_phase5?.mapped_requirements || []) {
    const reqId = req?.REQ_ID || req?.req_id;
    if (!reqId) continue;
    const compact = String(req?.functional_name || req?.label || toCompactModuleLabel(req?.description) || "").trim();
    if (!reqTitleMap[reqId] && compact && !isLikelyFilePath(compact) && compact !== "기능명 없음") {
      reqTitleMap[reqId] = compact;
    }
    reqFileRootMap[reqId] = extractFileRoot(req?.description, req?.mapping_reason, req?.layer_evidence);
  }

  const getBoundaryVisual = (boundary) => {
    const corpus = [boundary?.boundary_name, boundary?.crossing_data]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();

    if (/(client|web|electron|browser|ui)/.test(corpus)) {
      return { emoji: "🌐" };
    }
    if (/(llm|openai|gemini|model|ai)/.test(corpus)) {
      return { emoji: "🤖" };
    }
    if (/(chroma|vector|database|db|sqlite)/.test(corpus)) {
      return { emoji: "🗄️" };
    }
    if (/(device|local|desktop|on-device|on device)/.test(corpus)) {
      return { emoji: "💻" };
    }
    return { emoji: "🛡️" };
  };
  const normalizedRoles = ((sa_phase6.defined_roles || sa_phase6.rbac_roles || [])
    .map((role, idx) => {
      if (typeof role === "string") {
        return { role_name: role, description: "" };
      }
      return {
        role_name: role?.role_name || role?.name || `Role-${idx + 1}`,
        description: role?.description || "",
      };
    })
    .filter((role) => role.role_name));

  const normalizedBoundaries = ((sa_phase6.trust_boundaries || [])
    .map((boundary, idx) => {
      if (typeof boundary === "string") {
        return {
          boundary_name: boundary,
          crossing_data: "",
          security_controls: "",
        };
      }
      return {
        boundary_name: boundary?.boundary_name || boundary?.name || `Boundary-${idx + 1}`,
        crossing_data: boundary?.crossing_data || "",
        security_controls: boundary?.security_controls || boundary?.controls || "",
      };
    })
    .filter((boundary) => boundary.boundary_name));

  const normalizedAuthz = ((sa_phase6.authz_matrix || [])
    .map((row) => ({
      req_id: row?.req_id || row?.REQ_ID || "-",
      allowed_roles: Array.isArray(row?.allowed_roles)
        ? row.allowed_roles
        : row?.role
        ? [row.role]
        : [],
      restriction_level: row?.restriction_level || row?.access || "-",
    })));

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4">
      <Section title="보안 경계" icon={<Shield size={12} />}>
        <div className="flex items-center gap-2 mb-3">
          <StatusBadge status={sa_phase6.status || "Needs_Clarification"} />
        </div>

        {/* RBAC 역할 */}
        {normalizedRoles.length > 0 && (
          <div className="mb-3">
            <div className="text-[11px] text-slate-500 mb-1.5 uppercase tracking-wider">RBAC 역할</div>
            <div className="flex flex-wrap gap-2">
              {normalizedRoles.map((role) => (
                <span key={role.role_name} className="px-2.5 py-1 rounded-full bg-red-600/15 text-red-300 text-[12px] border border-red-800/30">
                  {role.role_name}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Trust Boundaries */}
        {normalizedBoundaries.length > 0 && (
          <div className="mb-3">
            <div className="text-[11px] text-slate-500 mb-1.5 uppercase tracking-wider">Trust Boundaries</div>
            <div className="space-y-1.5">
              {normalizedBoundaries.map((boundary, idx) => {
                const visual = getBoundaryVisual(boundary);
                return (
                  <div key={idx} className="rounded border border-slate-800/70 bg-slate-900/30 p-2">
                    <div className="flex items-center gap-1 text-[12px]">
                      <span className="text-[14px]" aria-hidden="true">{visual.emoji}</span>
                      <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300">{boundary.boundary_name}</span>
                    </div>
                    {boundary.crossing_data && (
                      <div className="mt-1 text-[12px] text-slate-400">
                        데이터: {boundary.crossing_data}
                      </div>
                    )}
                    {boundary.security_controls && (
                      <div className="mt-1 text-[12px] text-slate-500">
                        통제: {boundary.security_controls}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* authz_matrix 요약 */}
        {normalizedAuthz.length > 0 && (
          <div>
            <div className="text-[11px] text-slate-500 mb-1.5 uppercase tracking-wider">
              권한 매트릭스 ({normalizedAuthz.length}개)
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-[12px]">
                <thead>
                  <tr className="border-b border-slate-700">
                    <th className="text-left py-1 px-1 text-slate-500 font-medium">요구사항</th>
                    <th className="text-left py-1 px-1 text-slate-500 font-medium">Roles</th>
                    <th className="text-left py-1 px-1 text-slate-500 font-medium">Restriction</th>
                  </tr>
                </thead>
                <tbody>
                  {normalizedAuthz.slice(0, 16).map((row, idx) => {
                    const fileRoot = reqFileRootMap[row.req_id] || "-";
                    const functionName = reqTitleMap[row.req_id] || "";
                    const primaryLabel = functionName || fileRoot;
                    return (
                    <tr key={idx} className="border-b border-slate-800/50">
                      <td className="py-1 px-1">
                        <div className="text-slate-200 font-medium truncate">
                          {primaryLabel} <span className="text-slate-400">({row.req_id || "-"})</span>
                        </div>
                      </td>
                      <td className="py-1 px-1">
                        {row.allowed_roles.length > 0 ? (
                          <div className="flex flex-wrap gap-1">
                            {row.allowed_roles.map((role, roleIdx) => (
                              <span
                                key={`${role}-${roleIdx}`}
                                className="px-2 py-0.5 rounded-full bg-red-600/15 text-red-300 text-[11px] border border-red-800/30"
                              >
                                {role}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <span className="text-slate-600">-</span>
                        )}
                      </td>
                      <td className="py-1 px-1">
                        <span className={`px-1.5 py-0.5 rounded text-[11px] ${row.restriction_level === "Authorized" || row.restriction_level === "InternalOnly" ? "bg-orange-600/20 text-orange-300" : "bg-slate-700 text-slate-400"}`}>
                          {row.restriction_level}
                        </span>
                      </td>
                    </tr>
                    );
                  })}
                </tbody>
              </table>
              {normalizedAuthz.length > 16 && (
                <p className="text-[11px] text-slate-600 mt-1 text-right">
                  +{normalizedAuthz.length - 16}개 더 있음
                </p>
              )}
            </div>
          </div>
        )}
      </Section>
    </div>
  );
}

export default SASecurityTab;
