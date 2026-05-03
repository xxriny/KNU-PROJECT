import React from "react";
import { useStore } from "../../store/useStore";
import { 
  CheckCircle, Zap, Shield, Target, TrendingUp, BarChart, 
  Play, MessageSquare, X, Layout
} from "lucide-react";
import Card from "../ui/Card";
import Badge from "../ui/Badge";
import Button from "../ui/Button";
import ReportLayout, { ReportSection } from "./layout/ReportLayout";
import useAppStore from "../../store/useAppStore";

const OVERVIEW_KEYS = [
  'isDarkMode', 'resultData', 'userComments', 
  'removeComment', 'metadata',
  'pm_coverage_rate', 'sa_output'
];

const SECTION_MAP = {
  overview: "분석 개요",
  rtm: "요구사항(RTM)",
  stack: "기술 스택",
  sa_overview: "아키텍처 분석",
  sa_components: "컴포넌트 설계",
  sa_api: "API 설계",
  sa_db: "데이터베이스 설계",
  memo: "메모 관리",
};

export default function OverviewTab() {
  const { 
    isDarkMode, resultData, userComments, 
    removeComment, metadata,
    pm_coverage_rate, sa_output
  } = useStore(OVERVIEW_KEYS);
  
  const setChatInput = useAppStore(state => state.setChatInput);

  // 데이터가 하나라도 있으면 렌더링 시도 (가드 완화)
  const hasData = resultData || sa_output || metadata;

  if (!hasData) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-slate-500 animate-fade-in space-y-4">
        <div className="w-12 h-12 rounded-full border-2 border-slate-500/20 border-t-blue-500 animate-spin" />
        <p className="font-bold text-lg">데이터를 불러오는 중이거나 분석 결과가 없습니다.</p>
      </div>
    );
  }

  const metrics = resultData?.metrics || {};
  const analysis = resultData?.analysis || {};
  const recommendations = resultData?.recommendations || [];
  const saStatus = sa_output?.status || "UNKNOWN";
  
  const handleVerify = (comment) => {
    const userRequest = `사용자 지적사항 반영 및 재검증 요망: 기존 내용 "${comment.selectedText}" 에 대하여 "${comment.text}" 조치. 완료 후 애자일 파이프라인(PM/SA) 업데이트를 수행하세요.`;
    setChatInput(userRequest);
  };

  return (
    <ReportLayout
      icon={Layout}
      title="Analysis Overview"
      subtitle="프로젝트 전반의 아키텍처 점수와 핵심 지표, 그리고 AI가 제안하는 개선 권장사항 요약입니다."
      badge={metadata?.project_name || "Project Navigator"}
    >
      {/* Metrics Grid */}
      <ReportSection title="Project Health Metrics" icon={<BarChart size={20} />}>
        <div className="report-grid-3">
          <StatCard icon={Zap} label="Performance" value={`${metrics?.performance || 0}%`} color="blue" isDarkMode={isDarkMode} />
          <StatCard icon={Shield} label="Stability" value={`${metrics?.stability || 0}%`} color="emerald" isDarkMode={isDarkMode} />
          <StatCard icon={Target} label="Integrity" value={saStatus} color="amber" isDarkMode={isDarkMode} />
        </div>
      </ReportSection>

      {/* Core Insights */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <ReportSection title="Key Insights" icon={<TrendingUp size={20} />}>
          <Card variant="solid" className="p-8 h-full border-l-4 border-l-blue-500/30">
            <p className={`text-lg leading-relaxed font-medium ${isDarkMode ? "text-slate-300" : "text-slate-700"}`}>
              {analysis?.summary || resultData?.project_overview?.summary || "시스템 분석 결과를 종합하여 보고서를 작성하였습니다."}
            </p>
          </Card>
        </ReportSection>

        <ReportSection title="Recommendations" icon={<CheckCircle size={20} />}>
          <div className="space-y-4">
            {(recommendations || []).slice(0, 3).map((rec, i) => (
              <RecommendationCard key={i} rec={rec} isDarkMode={isDarkMode} />
            ))}
            {(!recommendations || recommendations.length === 0) && (
              <p className="text-slate-500 italic p-4 text-sm">현재 발견된 추가 권장사항이 없습니다.</p>
            )}
          </div>
        </ReportSection>
      </div>

      {/* User Feedback Management (RAG Learning Bridge) */}
      <ReportSection 
        title="RAG Learning Bridge" 
        icon={<MessageSquare size={20} className="text-blue-500" />} 
        badge={userComments?.length || 0}
      >
        {userComments?.length > 0 ? (
          <div className="space-y-4">
            {userComments.map(comment => (
              <Card key={comment.id} variant="glass" className="p-6 border-l-4 border-l-blue-500 ring-8 ring-blue-500/5 transition-all animate-fade-in">
                <div className="flex justify-between items-start mb-4">
                  <div className="space-y-1">
                    <span className="report-label-sm">In-Context Feedback</span>
                    <p className={`text-[11px] italic ${isDarkMode ? "text-slate-500" : "text-slate-400"}`}>
                      Ref: {SECTION_MAP[comment.section] || comment.section || "Global"}
                    </p>
                  </div>
                  <Button variant="ghost" size="sm" onClick={() => removeComment(comment.id)} className="h-8 w-8 !p-0"><X size={16} /></Button>
                </div>
                <p className={`font-bold text-xl leading-snug italic mb-6 ${isDarkMode ? "text-white" : "text-slate-900"}`}>"{comment.text}"</p>
                <div className="flex justify-end">
                  <Button variant="primary" onClick={() => handleVerify(comment)} Icon={Play}>검증 및 설계 반영</Button>
                </div>
              </Card>
            ))}
          </div>
        ) : (
          <div className={`flex flex-col items-center justify-center p-12 rounded-3xl border-2 border-dashed transition-colors ${
            isDarkMode ? "border-white/5 text-slate-600" : "border-slate-100 text-slate-400"
          }`}>
            <StickyNote size={32} className="mb-3 opacity-20" />
            <p className="text-sm italic">기록된 지적사항이나 메모가 없습니다. 설계 도면을 드래그하여 피드백을 추가하세요.</p>
          </div>
        )}
      </ReportSection>
    </ReportLayout>
  );
}

// 아이콘 임포트 누락 방지 (StickyNote 추가)
import { StickyNote } from "lucide-react";

const StatCard = React.memo(({ icon: Icon, label, value, color, isDarkMode }) => {
  const colors = {
    blue: "text-blue-500 bg-blue-500/10",
    emerald: "text-emerald-500 bg-emerald-500/10",
    amber: "text-amber-500 bg-amber-500/10",
  };
  return (
    <Card variant="solid" className="p-6 flex flex-col gap-4">
      <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${colors[color]}`}><Icon size={22} /></div>
      <div>
        <div className="report-label-sm mb-1">{label}</div>
        <div className={`text-3xl font-black ${isDarkMode ? "text-white" : "text-slate-900"}`}>{value}</div>
      </div>
    </Card>
  );
});

const RecommendationCard = React.memo(({ rec, isDarkMode }) => {
  const isCritical = rec.priority === "Critical";
  return (
    <Card variant="glass" noPadding className={`overflow-hidden border-l-4 ${isCritical ? "border-l-red-500" : "border-l-blue-500"}`}>
      <div className="p-5 flex gap-4">
        <Badge variant={isCritical ? "error" : "blue"} className="shrink-0 h-fit mt-1">{rec.priority}</Badge>
        <div className="space-y-1">
          <h4 className={`font-bold text-[15px] ${isDarkMode ? "text-white" : "text-slate-900"}`}>{rec.target}</h4>
          <p className={`text-[13px] leading-relaxed ${isDarkMode ? "text-slate-400" : "text-slate-600"}`}>{rec.action}</p>
        </div>
      </div>
    </Card>
  );
});
