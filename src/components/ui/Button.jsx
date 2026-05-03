import React from "react";
import useAppStore from "../../store/useAppStore";

const Button = ({
  children,
  onClick,
  variant = "primary", // primary, secondary, ghost, danger, outline
  size = "md", // sm, md, lg
  className = "",
  disabled = false,
  Icon,
  ...props
}) => {
  const isDarkMode = useAppStore(state => state.isDarkMode);

  const variants = {
    primary: "bg-blue-600 hover:bg-blue-700 text-white shadow-lg shadow-blue-500/20",
    secondary: isDarkMode 
      ? "bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700" 
      : "bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200",
    ghost: isDarkMode 
      ? "hover:bg-white/5 text-slate-400 hover:text-white" 
      : "hover:bg-black/5 text-slate-500 hover:text-slate-900",
    danger: "bg-red-500/10 hover:bg-red-500 text-red-500 hover:text-white border border-red-500/20",
    outline: isDarkMode
      ? "border border-slate-700 text-slate-300 hover:bg-slate-800"
      : "border border-slate-200 text-slate-600 hover:bg-slate-50",
  };

  const sizes = {
    sm: "px-2 py-1 text-xs gap-1.5",
    md: "px-4 py-2 text-sm gap-2",
    lg: "px-6 py-3 text-base gap-2.5",
  };

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`
        inline-flex items-center justify-center font-bold rounded-xl transition-all duration-200 active:scale-95
        ${variants[variant]}
        ${sizes[size]}
        ${disabled ? "opacity-50 cursor-not-allowed grayscale" : ""}
        ${className}
      `}
      {...props}
    >
      {Icon && <Icon size={size === "sm" ? 14 : 16} />}
      {children}
    </button>
  );
};

export default React.memo(Button);
