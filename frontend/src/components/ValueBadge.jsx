import React from "react";

const STYLES = {
  ACTUAL: { bg: "rgba(59,130,246,0.15)", text: "#60A5FA", border: "rgba(59,130,246,0.35)" },
  CONFIGURED: { bg: "rgba(16,185,129,0.15)", text: "#34D399", border: "rgba(16,185,129,0.35)" },
  IMPORTED: { bg: "rgba(14,165,233,0.15)", text: "#38BDF8", border: "rgba(14,165,233,0.35)" },
  UNCONFIGURED: { bg: "rgba(244,63,94,0.15)", text: "#FB7185", border: "rgba(244,63,94,0.35)" },
  ESTIMATED: { bg: "rgba(245,158,11,0.15)", text: "#FBBF24", border: "rgba(245,158,11,0.35)" },
  PROJECTED: { bg: "rgba(16,185,129,0.15)", text: "#34D399", border: "rgba(16,185,129,0.35)" },
  FORECAST: { bg: "rgba(139,92,246,0.15)", text: "#C084FC", border: "rgba(139,92,246,0.35)" },
  DEMO: { bg: "rgba(100,116,139,0.2)", text: "#CBD5E1", border: "rgba(100,116,139,0.4)" },
};

export function ValueBadge({ kind = "ACTUAL", className = "" }) {
  const s = STYLES[kind] || STYLES.ACTUAL;
  return (
    <span
      className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${className}`}
      style={{ background: s.bg, color: s.text, border: `1px solid ${s.border}` }}
      data-testid={`value-badge-${kind.toLowerCase()}`}
    >
      {kind}
    </span>
  );
}

export function ConfidenceBadge({ value, sources }) {
  const color = value >= 85 ? "#34D399" : value >= 70 ? "#FBBF24" : "#F87171";
  return (
    <div className="inline-flex items-center gap-2" title={sources ? `Based on: ${sources}` : undefined}>
      <div className="flex items-center gap-1.5">
        <div className="h-1.5 w-12 rounded-full bg-[#1E2235] overflow-hidden">
          <div className="h-full rounded-full" style={{ width: `${value}%`, background: color }} />
        </div>
        <span className="font-metric text-[11px] font-semibold" style={{ color }}>
          {value}%
        </span>
      </div>
      <span className="text-[10px] uppercase tracking-wide text-[#64748B]">AI confidence</span>
    </div>
  );
}
