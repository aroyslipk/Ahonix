import React from "react";
import { useQueryClient } from "@tanstack/react-query";
import { CheckSquare, Loader2, ShieldCheck, Info } from "lucide-react";
import { useSection } from "@/lib/hooks";
import { api, fmtCurrency } from "@/lib/api";
import { PageSkeleton, ErrorState } from "@/components/StateViews";
import { EmptyWorkspace } from "@/pages/Overview";
import { Card, SectionHeader } from "@/components/primitives";
import { ConfidenceBadge, ValueBadge } from "@/components/ValueBadge";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

const STAGE_CLS = {
  Detected: "bg-slate-800 text-slate-300 border-slate-700",
  Explained: "bg-cyan-950/50 text-cyan-300 border-cyan-800",
  Simulated: "bg-purple-950/50 text-purple-300 border-purple-800",
  "Awaiting Approval": "bg-amber-950/50 text-amber-300 border-amber-800",
  Approved: "bg-blue-950/50 text-blue-300 border-blue-800",
  Executed: "bg-emerald-950/50 text-emerald-300 border-emerald-800",
  Measured: "bg-emerald-900 text-emerald-200 border-emerald-500",
};

function nextOp(stage) {
  switch (stage) {
    case "Detected":
    case "Explained":
      return { op: "simulate", label: "Simulate" };
    case "Simulated":
    case "Awaiting Approval":
      return { op: "approve", label: "Approve" };
    case "Approved":
      return { op: "execute", label: "Execute (sandboxed)" };
    case "Executed":
      return { op: "measure", label: "Measure impact" };
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
        simulate: "Simulation complete — projected impact ready.",
        approve: "Action approved.",
        execute: "Executed in sandbox (no live external change).",
        measure: "Impact measured and recorded.",
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
        subtitle={`${pendingCount} recommendations awaiting your decision`}
        icon={CheckSquare}
        right={
          <span className="flex items-center gap-2 rounded-lg border border-amber-800/60 bg-amber-950/20 px-3 py-1.5 text-xs text-amber-300">
            <ShieldCheck size={14} /> Sandboxed — no live external actions
          </span>
        }
      />

      {/* lifecycle legend */}
      <Card className="p-4">
        <div className="flex flex-wrap items-center gap-1.5">
          {lifecycle.map((s, i) => (
            <React.Fragment key={s}>
              <span className={`rounded border px-2 py-1 text-[10px] font-semibold ${STAGE_CLS[s]}`}>{s}</span>
              {i < lifecycle.length - 1 && <span className="text-[#334155]">→</span>}
            </React.Fragment>
          ))}
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        {data.actions.map((a) => {
          const op = nextOp(a.stage);
          return (
            <Card key={a.action_id} className="p-5" data-testid={`action-card-${a.action_id}`}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <span className="text-[10px] font-medium uppercase tracking-wide text-[#64748B]">{a.category}</span>
                  <h3 className="font-display text-base font-bold text-[#F8FAFC]">{a.title}</h3>
                </div>
                <span className={`shrink-0 rounded border px-2 py-1 text-[10px] font-semibold ${STAGE_CLS[a.stage]}`} data-testid={`action-stage-${a.action_id}`}>
                  {a.stage}
                </span>
              </div>

              <p className="mt-2 text-sm text-[#94A3B8]">{a.description}</p>

              <div className="mt-4 grid grid-cols-2 gap-3">
                <div className="rounded-lg bg-[#0F111A] p-3">
                  <p className="text-[10px] uppercase tracking-wide text-[#64748B]">Current</p>
                  <p className="mt-0.5 font-metric text-sm font-semibold text-[#CBD5E1]">{a.current}</p>
                </div>
                <div className="rounded-lg bg-emerald-500/5 p-3">
                  <p className="text-[10px] uppercase tracking-wide text-emerald-400">Recommended</p>
                  <p className="mt-0.5 font-metric text-sm font-semibold text-emerald-300">{a.recommended}</p>
                </div>
              </div>

              <div className="mt-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="font-metric text-sm font-bold text-emerald-400">+{fmtCurrency(a.projected_impact, cur)}<span className="ml-1 text-xs font-medium text-[#64748B]">/{a.impact_period}</span></span>
                  <ValueBadge kind={a.impact_kind} />
                </div>
                <ConfidenceBadge value={a.confidence} />
              </div>

              {a.stage === "Executed" && (
                <div className="mt-3 flex items-center gap-2 rounded-lg border border-amber-800/40 bg-amber-950/10 px-3 py-2 text-xs text-amber-300">
                  <Info size={13} /> Simulated execution — no live integration was changed.
                </div>
              )}
              {a.stage === "Measured" && (
                <div className="mt-3 flex items-center gap-2 rounded-lg border border-emerald-800/40 bg-emerald-950/10 px-3 py-2 text-xs text-emerald-300">
                  <CheckSquare size={13} /> Measured impact: +{fmtCurrency(a.measured_impact, cur)}/{a.impact_period} (projected, demo).
                </div>
              )}

              {op && (
                <Button
                  onClick={() => run(a)}
                  disabled={busy === a.action_id}
                  className="mt-4 w-full bg-emerald-500 font-semibold text-emerald-950 hover:bg-emerald-400"
                  data-testid={a.stage === "Awaiting Approval" || a.stage === "Simulated" ? "action-center-approve-btn" : op.op === "simulate" ? "action-center-simulate-btn" : `action-${op.op}-btn`}
                >
                  {busy === a.action_id ? <Loader2 className="animate-spin" size={16} /> : op.label}
                </Button>
              )}
            </Card>
          );
        })}
      </div>
    </div>
  );
}
