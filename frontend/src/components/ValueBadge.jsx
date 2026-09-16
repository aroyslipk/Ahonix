import React from "react";

const STYLES = {
  ACTUAL: { bg: "rgba(0, 229, 153, 0.12)", text: "#00E599", border: "rgba(0, 229, 153, 0.3)" },
  CONFIGURED: { bg: "rgba(16, 185, 129, 0.12)", text: "#34D399", border: "rgba(16, 185, 129, 0.3)" },
  IMPORTED: { bg: "rgba(14, 165, 233, 0.12)", text: "#38BDF8", border: "rgba(14, 165, 233, 0.3)" },
  UNCONFIGURED: { bg: "rgba(244, 63, 94, 0.12)", text: "#FB7185", border: "rgba(244, 63, 94, 0.3)" },
  ESTIMATED: { bg: "rgba(245, 158, 11, 0.12)", text: "#FBBF24", border: "rgba(245, 158, 11, 0.3)" },
  PROJECTED: { bg: "rgba(0, 229, 153, 0.12)", text: "#00E599", border: "rgba(0, 229, 153, 0.3)" },
  FORECAST: { bg: "rgba(168, 85, 247, 0.12)", text: "#C084FC", border: "rgba(168, 85, 247, 0.3)" },
  DEMO: { bg: "rgba(100, 116, 139, 0.15)", text: "#94A3B8", border: "rgba(100, 116, 139, 0.3)" },
};

export function ValueBadge({ kind = "ACTUAL", className = "" }) {
  const s = STYLES[kind] || STYLES.ACTUAL;
  return (
    <span
      className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${className}`}
      style={{ background: s.bg, color: s.text, border: `1px solid ${s.border}` }}
      data-testid={`value-badge-${kind.toLowerCase()}`}
    >
      {kind}
    </span>
  );
}

export function ConfidenceBadge({ value, sources }) {
  const color = value >= 85 ? "#00E599" : value >= 70 ? "#FBBF24" : "#F87171";
  return (
    <div className="inline-flex items-center gap-2" title={sources ? `Verified against: ${sources}` : undefined}>
      <div className="flex items-center gap-1.5">
        <div className="h-1.5 w-12 overflow-hidden rounded-full bg-[#16221B]">
          <div className="h-full rounded-full" style={{ width: `${value}%`, background: color }} />
        </div>
        <span className="font-metric text-[11px] font-semibold" style={{ color }}>
          {value}%
        </span>
      </div>
      <span className="text-[10px] uppercase tracking-wider text-[#64748B]">Confidence</span>
    </div>
  );
}

