import React, { useMemo, useState } from "react";
import useAppStore from "../../store/useAppStore";
import { Section, EmptyState } from "./SharedComponents";
import { buildReqFunctionNameMap, layerBadgeTone } from "./resultUtils";
import { GitBranch, Shield } from "lucide-react";

export default function SAInterfacesTab() {
  const { sa_artifacts, sa_phase5 } = useAppStore();
  const doc = sa_artifacts?.interface_definition_doc;

  if (!doc) {
    return <EmptyState text="인터페이스 정의서 산출물이 없습니다" />;
  }

  const contracts = doc.contracts || [];
  const guardrails = doc.guardrails || [];
  const quality = doc.data_quality || {};
  const [expandedContractId, setExpandedContractId] = useState("");

  const reqFunctionNameMap = useMemo(
    () => buildReqFunctionNameMap(sa_phase5?.mapped_requirements),
    [sa_phase5?.mapped_requirements]
  );

  const formatIoPreview = (specText, maxLength = 86) => {
    const raw = String(specText || "").trim();
    if (!raw) return "-";
    const compact = raw.replace(/\s+/g, " ");
    return compact.length > maxLength ? `${compact.slice(0, maxLength)}...` : compact;
  };

  const formatExpandedIo = (specText) => {
    const raw = String(specText || "").trim();
    if (!raw) return "-";
    try {
      return JSON.stringify(JSON.parse(raw), null, 2);
    } catch {
      return raw;
    }
  };

  const renderGuardrailText = (text) => {
    const pattern = /(상호\s*TLS\s*\(mTLS\)\s*암호화|최소\s*권한\s*원칙|익명화\s*및\s*토큰화|토큰\s*회전|비밀\s*관리|감사\s*로그|입력\s*검증|권한\s*검사)/gi;
    const chunks = String(text || "").split(pattern);
    return chunks.map((chunk, idx) => {
      if (!chunk) return null;
      const highlighted = pattern.test(chunk);
      pattern.lastIndex = 0;
      return highlighted ? (
        <span key={`${chunk}-${idx}`} className="font-semibold text-amber-300">{chunk}</span>
      ) : (
        <span key={`${chunk}-${idx}`}>{chunk}</span>
      );
    });
  };

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4">
      <Section title="인터페이스 정의서" icon={<GitBranch size={12} />}>
        <div className="text-[12px] text-slate-500 mb-2">
          계약 {contracts.length}개 · 가드레일 {guardrails.length}개 · 완전성 {Math.round((quality.completeness || 0) * 100)}%
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-[12px] border-separate border-spacing-y-1">
            <thead>
              <tr className="border-b border-slate-700">
                <th className="text-left py-1 px-2 text-slate-500 font-medium">계약 ID</th>
                <th className="text-left py-1 px-2 text-slate-500 font-medium">레이어</th>
                <th className="text-left py-1 px-2 text-slate-500 font-medium">인터페이스</th>
                <th className="text-left py-1 px-2 text-slate-500 font-medium">Input</th>
                <th className="text-left py-1 px-2 text-slate-500 font-medium">Output</th>
                <th className="text-left py-1 px-2 text-slate-500 font-medium">상세</th>
              </tr>
            </thead>
            <tbody>
              {contracts.slice(0, 30).map((c, idx) => {
                const rowId = c.contract_id || `contract-${idx}`;
                const expanded = expandedContractId === rowId;
                const reqId = String(c.contract_id || "").startsWith("IF-")
                  ? String(c.contract_id).slice(3)
                  : String(c.contract_id || "");
                const contractLabel = reqFunctionNameMap[reqId] || c.interface_name || "-";
                return (
                  <React.Fragment key={rowId}>
                    <tr className="bg-slate-900/40 border border-slate-800/60">
                      <td className="py-2 px-2 align-top">
                        <div className="text-[13px] font-semibold text-slate-200 leading-snug">{contractLabel}</div>
                        <div className="mt-0.5 text-[11px] text-slate-500 font-mono">{c.contract_id || "-"}</div>
                      </td>
                      <td className="py-2 px-2 align-top">
                        <span className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] font-medium ${layerBadgeTone(c.layer)}`}>
                          {c.layer || "Unknown"}
                        </span>
                      </td>
                      <td className="py-2 px-2 align-top">
                        <div className="text-[13px] font-semibold text-slate-200 tracking-tight">{c.interface_name || "-"}</div>
                      </td>
                      <td className="py-2 px-2 align-top">
                        <div className="rounded-md bg-slate-800/30 px-2 py-1.5">
                          <code className="block max-w-[340px] truncate font-mono text-[11px] text-slate-400" title={c.input_spec || "-"}>
                            {formatIoPreview(c.input_spec)}
                          </code>
                        </div>
                      </td>
                      <td className="py-2 px-2 align-top">
                        <div className="rounded-md bg-slate-800/30 px-2 py-1.5">
                          <code className="block max-w-[360px] truncate font-mono text-[11px] text-slate-400" title={c.output_spec || "-"}>
                            {formatIoPreview(c.output_spec)}
                          </code>
                        </div>
                      </td>
                      <td className="py-2 px-2 align-top">
                        <button
                          type="button"
                          onClick={() => setExpandedContractId((prev) => (prev === rowId ? "" : rowId))}
                          className="text-[11px] px-2 py-1 rounded border border-slate-700 text-slate-300 hover:bg-slate-800"
                        >
                          {expanded ? "접기" : "펼치기"}
                        </button>
                      </td>
                    </tr>

                    {expanded && (
                      <tr className="bg-slate-950/40 border border-slate-800/60">
                        <td colSpan={6} className="px-2 pb-3 pt-1">
                          <div className="grid grid-cols-1 xl:grid-cols-2 gap-2">
                            <div className="rounded-md bg-slate-800/25 p-2">
                              <div className="text-[11px] uppercase tracking-wider text-slate-500 mb-1">Input (Full)</div>
                              <pre className="text-[11px] font-mono text-slate-300 whitespace-pre-wrap break-words leading-relaxed">
                                {formatExpandedIo(c.input_spec)}
                              </pre>
                            </div>
                            <div className="rounded-md bg-slate-800/25 p-2">
                              <div className="text-[11px] uppercase tracking-wider text-slate-500 mb-1">Output (Full)</div>
                              <pre className="text-[11px] font-mono text-slate-300 whitespace-pre-wrap break-words leading-relaxed">
                                {formatExpandedIo(c.output_spec)}
                              </pre>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      </Section>

      {guardrails.length > 0 && (
        <Section title="Guardrails" icon={<Shield size={12} />}>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-2">
            {guardrails.map((item, idx) => (
              <div key={idx} className="rounded-lg border border-slate-800/70 bg-slate-900/40 p-3">
                <div className="text-[11px] uppercase tracking-wider text-slate-500 mb-1">Rule {idx + 1}</div>
                <p className="text-[13px] text-slate-300 leading-relaxed">{renderGuardrailText(item)}</p>
              </div>
            ))}
          </div>
        </Section>
      )}
    </div>
  );
}
