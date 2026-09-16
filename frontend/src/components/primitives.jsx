import React from "react";

export function Card({ children, className = "", hover = false, ...rest }) {
  return (
    <div
      className={`rounded-xl border border-[#16221B] bg-[#0B110E] transition-all duration-200 ${
        hover ? "hover:border-emerald-500/30 hover:bg-[#0E1713]" : ""
      } ${className}`}
      {...rest}
    >
      {children}
    </div>
  );
}

export function SectionHeader({ title, subtitle, right, icon: Icon, className = "" }) {
  return (
    <div className={`flex flex-wrap items-end justify-between gap-3 ${className}`}>
      <div>
        <div className="flex items-center gap-2.5">
          {Icon && (
            <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-emerald-500/20 bg-emerald-500/10 text-emerald-400">
              <Icon size={16} />
            </span>
          )}
          <h2 className="font-display text-xl font-bold tracking-tight text-[#F8FAFC] sm:text-2xl">{title}</h2>
        </div>
        {subtitle && <p className="mt-1 text-sm text-[#94A3B8]">{subtitle}</p>}
      </div>
      {right}
    </div>
  );
}

export function Stat({ label, value, sub, className = "" }) {
  return (
    <div className={className}>
      <p className="text-xs font-medium uppercase tracking-wider text-[#64748B]">{label}</p>
      <p className="mt-1.5 font-metric text-2xl font-bold tracking-tight text-[#F8FAFC]">{value}</p>
      {sub && <p className="mt-1 text-xs text-[#94A3B8]">{sub}</p>}
    </div>
  );
}

export function DemoRibbon({ storeName }) {
  return (
    <div
      className="flex items-center gap-2 rounded-lg border border-emerald-500/20 bg-[#0B110E] px-3 py-1.5 text-xs text-[#94A3B8]"
      data-testid="demo-ribbon"
    >
      <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(0,229,153,0.6)]" />
      <span>Demo Workspace ·</span>
      <span className="font-semibold text-[#F8FAFC]">{storeName}</span>
    </div>
  );
}

