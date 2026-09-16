import React from "react";
import { useQueryClient } from "@tanstack/react-query";
import { CheckSquare, Loader2, ShieldCheck, Info, ArrowRight, Play, CheckCircle2, Sliders } from "lucide-react";
import { useSection } from "@/lib/hooks";
import { api, fmtCurrency } from "@/lib/api";
import { PageSkeleton, ErrorState } from "@/components/StateViews";
import { EmptyWorkspace } from "@/pages/Overview";
import { Card, SectionHeader } from "@/components/primitives";
import { ConfidenceBadge, ValueBadge } from "@/components/ValueBadge";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

const STAGE_CONFIG = {
  Detected: {
    badge: "border-[#1B2B22] bg-[#070C0A] text-[#94A3B8]",
    dot: "bg-slate-400",
  },
  Explained: {
    badge: "border-sky-500/30 bg-sky-500/10 text-sky-300",
    dot: "bg-sky-400",
  },
  Simulated: {
    badge: "border-indigo-500/30 bg-indigo-500/10 text-indigo-300",
    dot: "bg-indigo-400",
  },
  "Awaiting Approval": {
    badge: "border-[#D4AF37]/40 bg-[#D4AF37]/10 text-[#F5DE87]",
    dot: "bg-[#D4AF37]",
  },
  Approved: {
    badge: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
    dot: "bg-emerald-400",
  },
  Executed: {
    badge: "border-emerald-500/40 bg-emerald-500/15 text-[#00E599]",
    dot: "bg-[#00E599]",
  },
  Measured: {
    badge: "border-[#00E599]/60 bg-[#00E599]/20 text-[#00E599]",
    dot: "bg-[#00E599]",
  },
};

function nextOp(stage) {
  switch (stage) {
    case "Detected":
    case "Explained":
      return { op: "simulate", label: "Simulate Projected Impact", icon: Sliders };
    case "Simulated":
    case "Awaiting Approval":
      return { op: "approve", label: "Approve Recommendation", icon: CheckCircle2 };
    case "Approved":
      return { op: "execute", label: "Execute in Sandbox", icon: Play };
    case "Executed":
      return { op: "measure", label: "Measure Verified Impact", icon: CheckSquare };
    default:
      return null;
  }
}

export default function ActionCenter() {
  const qc = useQueryClient();
  const [busy, setBusy] = React.useState(null);
  const { data, isLoading, isError, refetch } = useSection("actions", "/actions");

  if (isLoading) return <PageSkeleton />;
  if (isError) return <ErrorState onRetry={refetch} />;
  if (data?.empty) return <EmptyWorkspace name={data.workspace?.name} />;

  const cur = data.workspace.currency;
  const lifecycle = data.lifecycle;

  const run = async (action) => {
    const op = nextOp(action.stage);
    if (!op) return;
    setBusy(action.action_id);
    try {
      const { data: res } = await api.post(`/actions/${action.action_id}`, { op: op.op });
      const messages = {
        simulate: "Simulation complete — projected financial impact calculated.",
        approve: "Action approved by merchant authority.",
        execute: "Executed in sandbox environment (zero live external risk).",
        measure: "Financial delta measured and logged to True Profit.",
      };
      toast.success(messages[op.op]);
      qc.setQueryData(["actions"], (old) => ({
        ...old,
        actions: old.actions.map((a) => (a.action_id === action.action_id ? res.action : a)),
      }));
    } catch {
      toast.error("Couldn't update this action.");
    } finally {
      setBusy(null);
    }
  };

  const pendingCount = data.actions.filter((a) => !["Executed", "Measured"].includes(a.stage)).length;

  return (
    <div className="space-y-8">
      <SectionHeader
        title="Action Center"
        subtitle={`${pendingCount} autonomous interventions awaiting merchant decision`}
        icon={CheckSquare}
        right={
          <span className="flex items-center gap-2 rounded-xl border border-[#D4AF37]/30 bg-[#D4AF37]/10 px-3.5 py-1.5 text-xs font-medium text-[#F5DE87]">
            <ShieldCheck size={14} className="text-[#D4AF37]" /> Sandboxed Execution Environment
          </span>
        }
      />

      {/* Lifecycle progression bar */}
      <Card className="p-4 border-[#16221B] bg-[#070C0A]">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-[#64748B]">
            Intervention Lifecycle
          </span>
          <div className="flex flex-wrap items-center gap-1.5">
            {lifecycle.map((s, i) => {
              const cfg = STAGE_CONFIG[s] || { badge: "border-[#1B2B22] bg-[#070C0A] text-[#94A3B8]", dot: "bg-slate-400" };
              return (
                <React.Fragment key={s}>
                  <span className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-[10px] font-semibold ${cfg.badge}`}>
                    <span className={`h-1.5 w-1.5 rounded-full ${cfg.dot}`} />
                    {s}
                  </span>
                  {i < lifecycle.length - 1 && <span className="text-[#1B2B22] text-xs">→</span>}
                </React.Fragment>
              );
            })}
          </div>
        </div>
      </Card>

      {/* Action cards grid */}
      <div className="grid gap-5 lg:grid-cols-2">
        {data.actions.map((a) => {
          const op = nextOp(a.stage);
          const cfg = STAGE_CONFIG[a.stage] || { badge: "border-[#1B2B22] bg-[#070C0A] text-[#94A3B8]", dot: "bg-slate-400" };
          const OpIcon = op?.icon;

          return (
            <Card
              key={a.action_id}
              className="p-6 border-[#16221B] bg-[#070C0A] flex flex-col justify-between transition-all hover:border-[#1F3327]"
              data-testid={`action-card-${a.action_id}`}
            >
              <div>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-[#00E599]/80">
                      {a.category}
                    </span>
                    <h3 className="mt-1 font-display text-base font-bold text-[#F8FAFC]">
                      {a.title}
                    </h3>
                  </div>
                  <span
                    className={`shrink-0 inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-[11px] font-semibold ${cfg.badge}`}
                    data-testid={`action-stage-${a.action_id}`}
                  >
                    <span className={`h-1.5 w-1.5 rounded-full ${cfg.dot}`} />
                    {a.stage}
                  </span>
                </div>

                <p className="mt-3 text-sm leading-relaxed text-[#94A3B8]">{a.description}</p>

                {/* State delta comparison */}
                <div className="mt-5 grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="rounded-xl border border-[#16221B] bg-[#0B110E] p-3.5">
                    <p className="text-[10px] font-semibold uppercase tracking-wider text-[#64748B]">Current State</p>
                    <p className="mt-1 font-metric text-sm font-semibold text-[#CBD5E1]">{a.current}</p>
                  </div>
                  <div className="rounded-xl border border-emerald-500/25 bg-emerald-500/5 p-3.5">
                    <p className="text-[10px] font-semibold uppercase tracking-wider text-[#00E599]">AHONIX Recommended</p>
                    <p className="mt-1 font-metric text-sm font-semibold text-[#00E599]">{a.recommended}</p>
                  </div>
                </div>

                {/* Projected financial delta */}
                <div className="mt-4 flex items-center justify-between border-t border-[#16221B] pt-4">
                  <div className="flex items-center gap-2">
                    <span className="font-metric text-base font-bold text-[#00E599]">
                      +{fmtCurrency(a.projected_impact, cur)}
                      <span className="ml-1 text-xs font-normal text-[#64748B]">/{a.impact_period}</span>
                    </span>
                    <ValueBadge kind={a.impact_kind} />
                  </div>
                  <ConfidenceBadge value={a.confidence} />
                </div>

                {/* Notice banners for sandboxed / measured states */}
                {a.stage === "Executed" && (
                  <div className="mt-4 flex items-center gap-2.5 rounded-xl border border-[#D4AF37]/30 bg-[#D4AF37]/10 px-3.5 py-2.5 text-xs text-[#F5DE87]">
                    <Info size={14} className="shrink-0 text-[#D4AF37]" />
                    <span>Simulated execution recorded in sandbox telemetry. Zero live store mutations occurred.</span>
                  </div>
                )}
                {a.stage === "Measured" && (
                  <div className="mt-4 flex items-center gap-2.5 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-3.5 py-2.5 text-xs text-[#00E599]">
                    <CheckSquare size={14} className="shrink-0 text-[#00E599]" />
                    <span>Verified financial yield: +{fmtCurrency(a.measured_impact, cur)}/{a.impact_period} reconciled.</span>
                  </div>
                )}
              </div>

              {/* Action trigger button */}
              {op && (
                <div className="mt-6 pt-2">
                  <Button
                    onClick={() => run(a)}
                    disabled={busy === a.action_id}
                    className="w-full rounded-xl bg-[#00E599] py-2.5 text-xs font-bold text-[#040706] hover:bg-[#00c984] transition-all shadow-[0_2px_12px_rgba(0,229,153,0.15)] active:scale-[0.99]"
                    data-testid={
                      a.stage === "Awaiting Approval" || a.stage === "Simulated"
                        ? "action-center-approve-btn"
                        : op.op === "simulate"
                        ? "action-center-simulate-btn"
                        : `action-${op.op}-btn`
                    }
                  >
                    {busy === a.action_id ? (
                      <span className="inline-flex items-center gap-2">
                        <Loader2 className="animate-spin" size={15} />
                        <span>Processing Intervention...</span>
                      </span>
                    ) : (
                      <span className="inline-flex items-center justify-center gap-2">
                        {OpIcon && <OpIcon size={14} />}
                        <span>{op.label}</span>
                      </span>
                    )}
                  </Button>
                </div>
              )}
            </Card>
          );
        })}
      </div>
    </div>
  );
}
