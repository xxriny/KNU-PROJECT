import React from "react";
import useAppStore from "../../store/useAppStore";

const Card = ({ 
  children, 
  className = "", 
  variant = "glass", // glass, solid, outline
  noPadding = false,
  onClick
}) => {
  const isDarkMode = useAppStore(state => state.isDarkMode);

  const variants = {
    glass: isDarkMode 
      ? "bg-slate-900/50 backdrop-blur-md border border-white/5" 
      : "bg-white/80 backdrop-blur-md border border-slate-200 shadow-sm",
    solid: isDarkMode 
      ? "bg-slate-900 border border-slate-800" 
      : "bg-slate-50 border border-slate-200",
    outline: "bg-transparent border border-[var(--border)]",
  };

  return (
    <div 
      onClick={onClick}
      className={`
        rounded-2xl transition-all
        ${variants[variant]}
        ${noPadding ? "" : "p-4"}
        ${onClick ? "cursor-pointer hover:border-blue-500/50 hover:shadow-lg hover:shadow-blue-500/5" : ""}
        ${className}
      `}
    >
      {children}
    </div>
  );
};

export default React.memo(Card);
