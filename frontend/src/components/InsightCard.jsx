import React from "react";
import {
  AlertTriangle, TrendingUp, ShieldAlert, ArrowRight, MessageSquare, Compass,
} from "lucide-react";
import { fmtCurrency } from "@/lib/api";
import { ConfidenceBadge, ValueBadge } from "@/components/ValueBadge";
import { Button } from "@/components/ui/button";

const SEV = {
  critical: { border: "border-l-rose-500", bg: "bg-[#0B110E]", icon: AlertTriangle, color: "text-rose-400", chip: "bg-rose-500/10 text-rose-300 border border-rose-500/20" },
  warning: { border: "border-l-amber-500", bg: "bg-[#0B110E]", icon: ShieldAlert, color: "text-amber-400", chip: "bg-amber-500/10 text-amber-300 border border-amber-500/20" },
  opportunity: { border: "border-l-emerald-500", bg: "bg-[#0B110E]", icon: TrendingUp, color: "text-emerald-400", chip: "bg-emerald-500/10 text-emerald-300 border border-emerald-500/20" },
};

const CTA_META = {
  Review: "review", Investigate: "investigate", Simulate: "simulate", Approve: "approve", Apply: "apply",
};

export function InsightCard({ insight, currency = "USD", category, onAsk, onAction, compact = false }) {
  const sev = SEV[insight.severity] || SEV.warning;
  const Icon = sev.icon;
  const impactPositive = insight.severity === "opportunity";
  const impactColor = impactPositive ? "text-emerald-400" : "text-rose-400";

  return (
    <div
      className={`rounded-xl border border-[#16221B] ${sev.bg} border-l-4 ${sev.border} p-5 transition-all duration-200 hover:border-[#1E2E25] hover:bg-[#0E1713]`}
      data-testid={`insight-card-${insight.id}`}
    >
      <div className="mb-3 flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className={`flex h-8 w-8 items-center justify-center rounded-lg border border-[#16221B] bg-[#070C0A] ${sev.color}`}>
            <Icon size={16} />
          </span>
          <div>
            <span className={`inline-flex rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${sev.chip}`}>
              {category || insight.severity}
            </span>
          </div>
        </div>
        <ConfidenceBadge value={insight.confidence} sources={insight.sources} />
      </div>

      <h3 className="font-display text-base font-bold leading-snug text-[#F8FAFC]">{insight.title}</h3>

      <div className="mt-2.5 flex flex-wrap items-center gap-2">
        <span className={`font-metric text-lg font-bold ${impactColor}`}>
          {impactPositive ? "+" : "-"}
          {fmtCurrency(Math.abs(insight.impact), currency)}
          <span className="ml-1 text-xs font-medium text-[#64748B]">/{insight.impact_period}</span>
        </span>
        <ValueBadge kind={insight.impact_kind} />
      </div>

      {!compact && (
        <>
          <ul className="mt-3.5 space-y-1.5">
            {insight.evidence?.map((e, i) => (
              <li key={i} className="flex items-start gap-2 text-xs text-[#94A3B8]">
                <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-[#344D3F]" />
                {e}
              </li>
            ))}
          </ul>
          <p className="mt-3 rounded-lg border border-[#16221B] bg-[#070C0A] p-3 text-xs leading-relaxed text-[#CBD5E1]">
            <span className="font-semibold text-[#94A3B8]">Reasoning: </span>
            {insight.reasoning}
          </p>
          <div className="mt-3 flex items-start gap-2 text-xs">
            <Compass size={14} className="mt-0.5 shrink-0 text-emerald-400" />
            <p className="text-[#CBD5E1]">
              <span className="font-semibold text-emerald-300">Action Plan: </span>
              {insight.recommendation}
            </p>
          </div>
        </>
      )}

      <div className="mt-4 flex flex-wrap gap-2">
        <Button
          size="sm"
          onClick={() => onAction?.(insight)}
          className="h-8 bg-emerald-500 font-semibold text-emerald-950 hover:bg-emerald-400"
          data-testid={`insight-cta-${insight.id}`}
        >
          {insight.action}
          <ArrowRight size={13} className="ml-1" />
        </Button>
        {onAsk && (
          <Button
            size="sm"
            variant="outline"
            onClick={() => onAsk(insight)}
            className="h-8 border-[#16221B] bg-[#070C0A] text-[#94A3B8] hover:border-emerald-500/30 hover:bg-[#0B110E] hover:text-[#F8FAFC]"
            data-testid={`insight-ask-${insight.id}`}
          >
            <MessageSquare size={13} className="mr-1.5 text-emerald-400" />
            Ask AHONIX
          </Button>
        )}
      </div>
    </div>
  );
}

export { CTA_META };

