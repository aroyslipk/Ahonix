import React from "react";

export function PremiumCard({
  children,
  className = "",
  header,
  badge,
  action,
  hoverable = true,
  elevated = false,
  ...props
}) {
  return (
    <div
      className={`relative rounded-2xl ${
        elevated ? "bg-[#0F1713] border-white/10 shadow-2xl" : "bg-[#0B110E] border-white/[0.07] shadow-xl"
      } border p-6 transition-all duration-200 ${
        hoverable ? "hover:border-emerald-500/30 hover:shadow-emerald-950/20" : ""
      } ${className}`}
      {...props}
    >
      {(header || badge || action) && (
        <div className="mb-5 flex items-center justify-between border-b border-white/[0.05] pb-4">
          <div className="flex items-center gap-2.5">
            {typeof header === "string" ? (
              <h3 className="font-display text-sm font-semibold tracking-wide text-[#F8FAFC]">
                {header}
              </h3>
            ) : (
              header
            )}
            {badge && (
              <span className="rounded bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-emerald-400">
                {badge}
              </span>
            )}
          </div>
          {action && <div>{action}</div>}
        </div>
      )}
      {children}
    </div>
  );
}
