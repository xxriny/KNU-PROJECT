import React from "react";
import useAppStore from "../../../store/useAppStore";
import Badge from "../../ui/Badge";

/**
 * ReportLayout - 결과 탭의 공통 레이아웃을 제공하는 컴포넌트
 * @param {Object} props
 * @param {React.ReactNode} props.icon - 제목 옆에 표시할 아이콘
 * @param {string} props.title - 탭의 대제목
 * @param {string} props.subtitle - 제목 아래 설명 문구
 * @param {string} props.badge - 대제목 옆에 표시할 뱃지 텍스트
 * @param {React.ReactNode} props.rightElement - 헤더 우측에 배치할 추가 요소 (예: 토글 버튼)
 * @param {React.ReactNode} props.children - 실제 탭의 내용
 */
const ReportLayout = ({ 
  icon: Icon, 
  title, 
  subtitle, 
  badge, 
  rightElement, 
  children 
}) => {
  const isDarkMode = useAppStore(state => state.isDarkMode);

  return (
    <div className="report-page-container">
      {/* Tab Header Section */}
      <header className="flex flex-col md:flex-row md:items-end justify-between gap-8 px-1">
        <div className="space-y-4">
          <div className="report-header-badge-group">
            {Icon && <Icon className="text-blue-500" size={24} />}
            {badge && <Badge variant="blue" className="px-3 py-1 text-xs">{badge}</Badge>}
          </div>
          <h1 className={`report-title ${isDarkMode ? "text-white" : "text-slate-900"}`}>
            {title}
          </h1>
          {subtitle && (
            <p className="report-subtitle">
              {subtitle}
            </p>
          )}
        </div>
        {rightElement && (
          <div className="pb-2">
            {rightElement}
          </div>
        )}
      </header>

      {/* Main Content Area */}
      <main className="space-y-16">
        {children}
      </main>
    </div>
  );
};

/**
 * ReportSection - 리포트 내의 섹션 구분
 */
export const ReportSection = ({ title, icon: Icon, children, badge }) => {
  const isDarkMode = useAppStore(state => state.isDarkMode);
  
  return (
    <section className="animate-fade-in animate-slide-up">
      <div className="report-section-title-group">
        {Icon && <div className="text-blue-500">{Icon}</div>}
        <h3 className={`report-section-title ${isDarkMode ? "text-slate-200" : "text-slate-800"}`}>
          {title}
        </h3>
        {badge && <Badge variant="secondary" className="ml-2">{badge}</Badge>}
      </div>
      {children}
    </section>
  );
};

export default React.memo(ReportLayout);
