import React from "react";

export function Card({ children, className = "", hover = false, ...rest }) {
  return (
    <div
      className={`rounded-xl border border-[#1E2235] bg-[#121420] ${hover ? "card-hover" : ""} ${className}`}
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
        <div className="flex items-center gap-2">
          {Icon && (
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-400">
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
      <p className="text-xs font-medium text-[#64748B]">{label}</p>
      <p className="mt-1 font-metric text-xl font-bold text-[#F8FAFC]">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-[#94A3B8]">{sub}</p>}
    </div>
  );
}

export function DemoRibbon({ storeName }) {
  return (
    <div
      className="flex items-center gap-2 rounded-lg border border-[#2D334B] bg-[#0F111A] px-3 py-1.5 text-xs text-[#94A3B8]"
      data-testid="demo-ribbon"
    >
      <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
      Demo Workspace · <span className="font-semibold text-[#F8FAFC]">{storeName}</span>
    </div>
  );
}
