import React from "react";
import { ArrowUpRight, ArrowDownRight, Info } from "lucide-react";
import { fmtValue } from "@/lib/api";
import { Sparkline } from "@/components/charts";
import { ValueBadge } from "@/components/ValueBadge";
import {
  Tooltip, TooltipContent, TooltipProvider, TooltipTrigger,
} from "@/components/ui/tooltip";

export function KpiCard({ kpi, currency, onClick }) {
  const positive = kpi.invert ? kpi.change < 0 : kpi.change >= 0;
  const changeColor = positive ? "text-emerald-400" : "text-rose-400";
  const changeBg = positive ? "bg-emerald-500/10 border-emerald-500/20" : "bg-rose-500/10 border-rose-500/20";
  const Arrow = kpi.change >= 0 ? ArrowUpRight : ArrowDownRight;
  const sparkColor = positive ? "#00E599" : "#F43F5E";

  return (
    <div
      onClick={onClick}
      className={`group relative overflow-hidden rounded-xl border border-[#16221B] bg-[#0B110E] p-5 transition-all duration-200 hover:border-emerald-500/30 hover:bg-[#0E1713] ${
        onClick ? "cursor-pointer" : ""
      }`}
      data-testid={`kpi-card-${kpi.id}`}
    >
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-xs font-medium text-[#94A3B8]">
          {kpi.label}
          <TooltipProvider delayDuration={120}>
            <Tooltip>
              <TooltipTrigger asChild>
                <span className="cursor-help text-[#475569] hover:text-[#94A3B8]">
                  <Info size={12} />
                </span>
              </TooltipTrigger>
              <TooltipContent className="max-w-[220px] border-[#16221B] bg-[#070C0A] text-xs text-[#CBD5E1]">
                {kpi.tooltip}
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
        <ValueBadge kind={kpi.kind} />
      </div>

      <div className="flex items-end justify-between gap-3">
        <div>
          <p className="font-metric text-2xl font-bold tracking-tight text-[#F8FAFC] sm:text-3xl">
            {kpi.id === "marketing-eff" && (!kpi.value || kpi.value === 0)
              ? "—"
              : fmtValue(kpi.format, kpi.value, currency)}
          </p>
          <div className="mt-2.5 flex items-center gap-2 text-xs">
            {kpi.id === "marketing-eff" && (!kpi.value || kpi.value === 0) ? (
              <span className="text-[#64748B]">
                {kpi.kind === "CONFIGURED" ? "No eligible ad spend" : "No ad accounts connected"}
              </span>
            ) : (
              <>
                <span className={`inline-flex items-center rounded border px-1.5 py-0.5 font-semibold ${changeColor} ${changeBg}`}>
                  <Arrow size={12} className="mr-0.5" />
                  {Math.abs(kpi.change).toFixed(1)}%
                </span>
                <span className="text-[#64748B]">vs prev period</span>
              </>
            )}
          </div>
        </div>
        <div className="h-10 w-24 shrink-0 opacity-90">
          {kpi.id === "marketing-eff" && (!kpi.value || kpi.value === 0) ? null : (
            <Sparkline data={kpi.spark} color={sparkColor} />
          )}
        </div>
      </div>
    </div>
  );
}

