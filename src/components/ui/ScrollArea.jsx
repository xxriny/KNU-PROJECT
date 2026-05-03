import React from "react";

export default function ScrollArea({ children, className = "", horizontal = false }) {
  return (
    <div className={`
      overflow-auto custom-scrollbar
      ${horizontal ? "overflow-y-hidden" : "overflow-x-hidden"}
      ${className}
    `}>
      {children}
    </div>
  );
}
