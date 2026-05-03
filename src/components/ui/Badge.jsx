import React from "react";

const Badge = ({ 
  children, 
  variant = "default", // default, success, error, warning, blue
  className = "" 
}) => {
  const variants = {
    default: "bg-slate-500/10 text-slate-500 border-slate-500/20",
    success: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20",
    error: "bg-red-500/10 text-red-500 border-red-500/20",
    warning: "bg-amber-500/10 text-amber-500 border-amber-500/20",
    blue: "bg-blue-500/10 text-blue-500 border-blue-500/20",
    secondary: "bg-white/5 text-slate-400 border-white/5",
  };

  return (
    <span className={`
      inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider border
      ${variants[variant] || variants.default}
      ${className}
    `}>
      {children}
    </span>
  );
};

export default React.memo(Badge);
