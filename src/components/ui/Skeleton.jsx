import React from "react";
import useAppStore from "../../store/useAppStore";

const Skeleton = ({ className = "", variant = "rect" }) => {
  const isDarkMode = useAppStore((state) => state.isDarkMode);
  
  const baseClass = isDarkMode ? "bg-slate-800/50" : "bg-slate-200/50";
  const shapeClass = variant === "circle" ? "rounded-full" : "rounded-lg";

  return (
    <div className={`
      animate-pulse ${baseClass} ${shapeClass} ${className}
    `} />
  );
};

export default React.memo(Skeleton);
