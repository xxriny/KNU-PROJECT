import React from "react";
import {
  AlertTriangle,
  BarChart,
  CheckCircle,
  CheckCircle2,
  Database,
  GitBranch,
  Layout,
  MessageSquare,
  Play,
  Shield,
  StickyNote,
  Target,
  TrendingUp,
  X,
  Zap,
} from "lucide-react";
import { useStore } from "../../store/useStore";
import useAppStore from "../../store/useAppStore";
import Card from "../ui/Card";
import Badge from "../ui/Badge";
import Button from "../ui/Button";
import ReportLayout, { ReportSection } from "./layout/ReportLayout";

const OVERVIEW_KEYS = [
  "isDarkMode",
  "resultData",
  "userComments",
  "removeComment",
  "metadata",
  "sa_output"
];

const SECTION_MAP = {
  overview: "Overview",
  rtm: "RTM",
  stack: "Stack",
  sa_overview: "SA Overview",
  sa_components: "SA Components",
  sa_api: "SA API",
  sa_db: "SA Database",
  memo: "Memo",
};

export default function OverviewTab() {
  const {
    isDarkMode,
    resultData,
    userComments,
    removeComment,
    metadata,
    sa_output
  } = useStore(OVERVIEW_KEYS);
  const setChatInput = useAppStore((state) => state.setChatInput);

  const hasData = resultData || sa_output || metadata;

  if (!hasData) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-slate-500 animate-fade-in space-y-4">
        <div className="w-12 h-12 rounded-full border-2 border-slate-500/20 border-t-blue-500 animate-spin" />
        <p className="font-bold text-lg">결과 데이터가 아직 없습니다.</p>
      </div>
    );
  }

  const metrics = resultData?.metrics || {};
  const analysis = resultData?.analysis || {};
  const recommendations = resultData?.recommendations || [];
  const saStatus = sa_output?.status || "UNKNOWN";
  const pipelineType = resultData?.pipeline_type || "";
  const isDevelop = pipelineType === "develop_plan";
  const developOverview = resultData?.develop_overview || resultData?.dev_overview || {};
  const branchPrResult = resultData?.branch_pr_result || {};
  const embeddingResult = resultData?.embedding_result || {};

  const handleVerify = (comment) => {
    const userRequest = `기존 내용 "${comment.selectedText}"를 기준으로 "${comment.text}"를 반영하도록 후속 분석을 진행해줘.`;
    setChatInput(userRequest);
  };

  return (
    <ReportLayout
      icon={Layout}
      title={isDevelop ? "Develop Overview" : "Analysis Overview"}
      subtitle={
        isDevelop
          ? "개발 파이프라인의 진행 상태, 브랜치/PR 준비 상태, embedding 적재 결과를 요약합니다."
          : "프로젝트 분석 결과와 아키텍처 상태, 권장 조치들을 요약합니다."
      }
      badge={metadata?.project_name || "Project Navigator"}
    >
      {isDevelop && (
        <>
          <ReportSection title="Develop Pipeline" icon={<BarChart size={20} />}>
            <div className="report-grid-3">
              <StatCard icon={Target} label="Goal" value={developOverview?.goal || "-"} color="blue" isDarkMode={isDarkMode} compact />
              <StatCard icon={GitBranch} label="Branch / PR" value={developOverview?.branch_pr_status || "-"} color="emerald" isDarkMode={isDarkMode} />
              <StatCard icon={Database} label="Embedding" value={developOverview?.embedding_status || "-"} color="amber" isDarkMode={isDarkMode} />
            </div>
          </ReportSection>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">
            <ReportSection title="Branch And PR" icon={<GitBranch size={20} />} badge={branchPrResult?.feature_branches?.length || 0}>
              <div className="space-y-4">
                <KeyValueRows
                  rows={[
                    ["Status", branchPrResult?.status || "-"],
                    ["Base Branch", branchPrResult?.base_branch || "-"],
                    ["Resolved Ref", branchPrResult?.resolved_base_ref || "-"],
                    ["Merge Ready", branchPrResult?.merge_ready ? "true" : "false"],
                  ]}
                  isDarkMode={isDarkMode}
                />
                <ListCard
                  title="Feature Branches"
                  items={(branchPrResult?.feature_branches || []).map((item) => `${item.domain}: ${item.branch}`)}
                  emptyText="생성된 feature branch가 없습니다."
                  isDarkMode={isDarkMode}
                />
                <ListCard
                  title="PR Draft Commands"
                  items={(branchPrResult?.pr_drafts || []).map((item) => item.create_command)}
                  emptyText="생성된 PR draft가 없습니다."
                  isDarkMode={isDarkMode}
                  mono
                />
              </div>
            </ReportSection>

            <ReportSection title="Embedding Persistence" icon={<Database size={20} />} badge={embeddingResult?.persisted_artifacts?.length || 0}>
              <div className="space-y-4">
                <KeyValueRows
                  rows={[
                    ["Status", embeddingResult?.status || "-"],
                    ["Session", embeddingResult?.session_id || "-"],
                    ["Source Session", embeddingResult?.source_session_id || "-"],
                    ["Collections", (embeddingResult?.target_collections || []).join(", ") || "-"],
                  ]}
                  isDarkMode={isDarkMode}
                />
                <ListCard
                  title="Persisted Artifacts"
                  items={(embeddingResult?.persisted_artifacts || []).map((item) => `${item.artifact_type}: ${item.chunk_id}`)}
                  emptyText="적재된 artifact가 없습니다."
                  isDarkMode={isDarkMode}
                  success
                />
                <ListCard
                  title="Errors"
                  items={embeddingResult?.errors || []}
                  emptyText="오류가 없습니다."
                  isDarkMode={isDarkMode}
                  danger={Boolean(embeddingResult?.errors?.length)}
                />
              </div>
            </ReportSection>
          </div>

          <ReportSection title="Domain Status" icon={<CheckCircle2 size={20} />}>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {["uiux", "backend", "frontend"].map((domain) => (
                <DomainStatusCard
                  key={domain}
                  domain={domain}
                  result={developOverview?.domain_status?.[domain]}
                  qa={developOverview?.qa_status?.[domain]}
                  gate={developOverview?.domain_gate_status?.[domain]}
                  isDarkMode={isDarkMode}
                />
              ))}
            </div>
          </ReportSection>
        </>
      )}

      <ReportSection title="Project Health Metrics" icon={<BarChart size={20} />}>
        <div className="report-grid-3">
          <StatCard icon={Zap} label="Performance" value={`${metrics?.performance || 0}%`} color="blue" isDarkMode={isDarkMode} />
          <StatCard icon={Shield} label="Stability" value={`${metrics?.stability || 0}%`} color="emerald" isDarkMode={isDarkMode} />
          <StatCard icon={Target} label="Integrity" value={saStatus} color="amber" isDarkMode={isDarkMode} />
        </div>
      </ReportSection>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <ReportSection title="Key Insights" icon={<TrendingUp size={20} />}>
          <Card variant="solid" className="p-8 h-full border-l-4 border-l-blue-500/30">
            <p className={`text-lg leading-relaxed font-medium ${isDarkMode ? "text-slate-300" : "text-slate-700"}`}>
              {analysis?.summary || resultData?.project_overview?.summary || "분석 결과 요약이 아직 없습니다."}
            </p>
          </Card>
        </ReportSection>

        <ReportSection title="Recommendations" icon={<CheckCircle size={20} />}>
          <div className="space-y-4">
            {recommendations.slice(0, 3).map((rec, index) => (
              <RecommendationCard key={index} rec={rec} isDarkMode={isDarkMode} />
            ))}
            {recommendations.length === 0 && (
              <p className="text-slate-500 italic p-4 text-sm">추가 권장사항이 없습니다.</p>
            )}
          </div>
        </ReportSection>
      </div>

      <ReportSection title="RAG Learning Bridge" icon={<MessageSquare size={20} className="text-blue-500" />} badge={userComments?.length || 0}>
        {userComments?.length > 0 ? (
          <div className="space-y-4">
            {userComments.map((comment) => (
              <Card key={comment.id} variant="glass" className="p-6 border-l-4 border-l-blue-500 ring-8 ring-blue-500/5 transition-all animate-fade-in">
                <div className="flex justify-between items-start mb-4">
                  <div className="space-y-1">
                    <span className="report-label-sm">In-Context Feedback</span>
                    <p className={`text-[11px] italic ${isDarkMode ? "text-slate-500" : "text-slate-400"}`}>
                      Ref: {SECTION_MAP[comment.section] || comment.section || "Global"}
                    </p>
                  </div>
                  <Button variant="ghost" size="sm" onClick={() => removeComment(comment.id)} className="h-8 w-8 !p-0">
                    <X size={16} />
                  </Button>
                </div>
                <p className={`font-bold text-xl leading-snug italic mb-6 ${isDarkMode ? "text-white" : "text-slate-900"}`}>
                  "{comment.text}"
                </p>
                <div className="flex justify-end">
                  <Button variant="primary" onClick={() => handleVerify(comment)} Icon={Play}>
                    반영 요청
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        ) : (
          <div className={`flex flex-col items-center justify-center p-12 rounded-3xl border-2 border-dashed transition-colors ${
            isDarkMode ? "border-white/5 text-slate-600" : "border-slate-100 text-slate-400"
          }`}>
            <StickyNote size={32} className="mb-3 opacity-20" />
            <p className="text-sm italic">아직 저장된 메모가 없습니다.</p>
          </div>
        )}
      </ReportSection>
    </ReportLayout>
  );
}

const StatCard = React.memo(({ icon: Icon, label, value, color, isDarkMode, compact = false }) => {
  const colors = {
    blue: "text-blue-500 bg-blue-500/10",
    emerald: "text-emerald-500 bg-emerald-500/10",
    amber: "text-amber-500 bg-amber-500/10",
  };

  return (
    <Card variant="solid" className="p-6 flex flex-col gap-4">
      <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${colors[color]}`}>
        <Icon size={22} />
      </div>
      <div>
        <div className="report-label-sm mb-1">{label}</div>
        <div className={`${compact ? "text-xl" : "text-3xl"} font-black break-words ${isDarkMode ? "text-white" : "text-slate-900"}`}>
          {value}
        </div>
      </div>
    </Card>
  );
});

const RecommendationCard = React.memo(({ rec, isDarkMode }) => {
  const isCritical = rec.priority === "Critical";

  return (
    <Card variant="glass" noPadding className={`overflow-hidden border-l-4 ${isCritical ? "border-l-red-500" : "border-l-blue-500"}`}>
      <div className="p-5 flex gap-4">
        <Badge variant={isCritical ? "error" : "blue"} className="shrink-0 h-fit mt-1">
          {rec.priority}
        </Badge>
        <div className="space-y-1">
          <h4 className={`font-bold text-[15px] ${isDarkMode ? "text-white" : "text-slate-900"}`}>{rec.target}</h4>
          <p className={`text-[13px] leading-relaxed ${isDarkMode ? "text-slate-400" : "text-slate-600"}`}>{rec.action}</p>
        </div>
      </div>
    </Card>
  );
});

function KeyValueRows({ rows, isDarkMode }) {
  return (
    <Card variant="solid" className="p-5 space-y-3">
      {rows.map(([label, value]) => (
        <div key={label} className="flex items-start justify-between gap-4">
          <span className="report-label-sm">{label}</span>
          <span className={`text-right text-sm font-medium break-all ${isDarkMode ? "text-slate-300" : "text-slate-700"}`}>
            {value}
          </span>
        </div>
      ))}
    </Card>
  );
}

function ListCard({ title, items, emptyText, isDarkMode, mono = false, success = false, danger = false }) {
  return (
    <Card
      variant="glass"
      className={`p-5 border-l-4 ${danger ? "border-l-red-500" : success ? "border-l-emerald-500" : "border-l-blue-500"}`}
    >
      <div className="report-label-sm mb-3">{title}</div>
      {items?.length ? (
        <div className="space-y-2">
          {items.map((item, index) => (
            <div
              key={`${title}_${index}`}
              className={`text-sm break-all ${mono ? "font-mono" : "font-medium"} ${isDarkMode ? "text-slate-300" : "text-slate-700"}`}
            >
              {item}
            </div>
          ))}
        </div>
      ) : (
        <div className={`text-sm ${danger ? "text-red-400" : isDarkMode ? "text-slate-500" : "text-slate-500"}`}>
          {emptyText}
        </div>
      )}
    </Card>
  );
}

function DomainStatusCard({ domain, result, qa, gate, isDarkMode }) {
  const rows = [
    ["Result", result || "-"],
    ["QA", qa || "-"],
    ["Gate", gate || "-"],
  ];

  return (
    <Card variant="solid" className="p-5">
      <div className="flex items-center gap-2 mb-4">
        <AlertTriangle size={16} className="text-blue-400" />
        <h4 className={`text-sm font-black uppercase tracking-wide ${isDarkMode ? "text-white" : "text-slate-900"}`}>
          {domain}
        </h4>
      </div>
      <div className="space-y-3">
        {rows.map(([label, value]) => (
          <div key={label} className="flex items-center justify-between gap-3">
            <span className="report-label-sm">{label}</span>
            <span className={`text-sm font-medium ${isDarkMode ? "text-slate-300" : "text-slate-700"}`}>{value}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}
