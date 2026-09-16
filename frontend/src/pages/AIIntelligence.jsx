import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Activity, Check, Loader2, TrendingDown, TrendingUp,
  ShieldAlert, Users, Boxes, ArrowRight, Wallet, ShieldCheck,
} from "lucide-react";
import { useSection } from "@/lib/hooks";
import { useUI } from "@/context/UIContext";
import { PageSkeleton, ErrorState } from "@/components/StateViews";
import { EmptyWorkspace } from "@/pages/Overview";
import { InsightCard } from "@/components/InsightCard";
import { Card, SectionHeader } from "@/components/primitives";
import { Button } from "@/components/ui/button";

const DATASETS = ["Sales", "Products", "Marketing", "Inventory", "Customers", "Returns", "Operations", "Payments"];

const GROUPS = [
  { key: "money_leaks", label: "Money Leaks", icon: TrendingDown, color: "text-rose-400" },
  { key: "growth_opportunities", label: "Growth Opportunities", icon: TrendingUp, color: "text-emerald-400" },
  { key: "operational_risks", label: "Operational Risks", icon: ShieldAlert, color: "text-amber-400" },
  { key: "customer_issues", label: "Customer Issues", icon: Users, color: "text-sky-400" },
  { key: "inventory_risks", label: "Inventory Risks", icon: Boxes, color: "text-purple-400" },
];

function ScanSequence({ onDone }) {
  const [phase, setPhase] = useState("connecting");
  const [checked, setChecked] = useState(0);

  useEffect(() => {
    if (phase === "connecting") {
      if (checked < DATASETS.length) {
        const t = setTimeout(() => setChecked((c) => c + 1), 220);
        return () => clearTimeout(t);
      }
      const t = setTimeout(() => setPhase("analyzing"), 300);
      return () => clearTimeout(t);
    }
    if (phase === "analyzing") {
      const t = setTimeout(onDone, 1500);
      return () => clearTimeout(t);
    }
  }, [phase, checked, onDone]);

  return (
    <div className="flex flex-col items-center py-12 text-center" data-testid="xray-scanning">
      {/* Clean Diagnostic Pulse */}
      <div className="relative mb-6 flex h-24 w-24 items-center justify-center">
        <div className="absolute inset-0 rounded-full border border-emerald-500/20 bg-emerald-500/5 animate-ping opacity-30" />
        <div className="relative z-10 flex h-16 w-16 items-center justify-center rounded-2xl border border-emerald-500/30 bg-[#0B1A13] text-emerald-400 shadow-[0_0_24px_rgba(0,229,153,0.2)]">
          <Activity size={28} />
        </div>
      </div>

      {phase === "connecting" ? (
        <>
          <h2 className="font-display text-lg font-bold text-[#F8FAFC]">Verifying Merchant Telemetry</h2>
          <p className="mt-1 text-xs text-[#94A3B8]">Auditing cross-system records for complete financial integrity</p>
          <div className="mt-6 grid w-full max-w-md grid-cols-2 gap-2 sm:grid-cols-4">
            {DATASETS.map((d, i) => (
              <div
                key={d}
                className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-xs font-medium transition-all ${
                  i < checked ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300" : "border-[#16221B] bg-[#070C0A] text-[#64748B]"
                }`}
              >
                {i < checked ? <Check size={13} className="text-emerald-400 stroke-[2.5]" /> : <Loader2 size={13} className="animate-spin text-[#475569]" />}
                {d}
              </div>
            ))}
          </div>
        </>
      ) : (
        <>
          <h2 className="font-display text-lg font-bold text-[#F8FAFC]">Correlating Multidimensional Signals</h2>
          <p className="mt-1 text-xs text-[#94A3B8]">Synthesizing True Profit impact, ad ROAS variances, and inventory turns</p>
        </>
      )}
    </div>
  );
}

export default function AIIntelligence() {
  const navigate = useNavigate();
  const { openAsk } = useUI();
  const [scanning, setScanning] = useState(false);
  const [revealed, setRevealed] = useState(false);
  const { data, isLoading, isError, refetch } = useSection("intelligence", "/intelligence");

  if (isLoading) return <PageSkeleton />;
  if (isError) return <ErrorState onRetry={refetch} />;
  if (data?.empty) return <EmptyWorkspace name={data.workspace?.name} />;

  const cur = data.workspace.currency;
  const insights = data.insights;
  const total = GROUPS.reduce((n, g) => n + (insights[g.key]?.length || 0), 0);

  const onAction = (insight) => {
    if (["Approve", "Simulate", "Apply"].includes(insight.action)) navigate("/app/action-center");
    else navigate("/app/action-center");
  };

  return (
    <div className="space-y-8" data-testid="ai-intelligence-page">
      <SectionHeader
        title="Business Diagnostic Engine"
        subtitle="Cross-system correlation of revenue, unit margins, customer friction, and advertising efficiency"
        icon={Activity}
        right={
          <Button
            onClick={() => navigate("/app/profit")}
            variant="outline"
            className="border-[#16221B] bg-[#0B110E] text-xs text-[#94A3B8] hover:border-emerald-500/30 hover:bg-[#0E1713] hover:text-[#F8FAFC]"
            data-testid="open-profit-btn"
          >
            <Wallet size={14} className="mr-1.5 text-emerald-400" /> True Profit Engine
          </Button>
        }
      />

      {!revealed && (
        <Card className="p-6 sm:p-8">
          {scanning ? (
            <ScanSequence onDone={() => { setScanning(false); setRevealed(true); }} />
          ) : (
            <div className="flex flex-col items-center py-8 text-center">
              <span className="mb-5 flex h-14 w-14 items-center justify-center rounded-2xl border border-emerald-500/20 bg-emerald-500/10 text-emerald-400">
                <ShieldCheck size={26} />
              </span>
              <h2 className="font-display text-2xl font-bold text-[#F8FAFC]">Initiate Operations Audit</h2>
              <p className="mt-2 max-w-lg text-xs leading-relaxed text-[#94A3B8]">
                AHONIX cross-references 8 commerce telemetry streams to uncover verified profit leaks, high-probability growth levers, and inventory risks with complete audit trails.
              </p>
              <Button
                onClick={() => setScanning(true)}
                className="mt-6 bg-emerald-500 px-6 font-semibold text-emerald-950 hover:bg-emerald-400"
                data-testid="business-xray-scan-btn"
              >
                <Activity size={15} className="mr-2" /> Start Diagnostic Audit
              </Button>
            </div>
          )}
        </Card>
      )}

      {revealed && (
        <>
          <div className="rounded-xl border border-emerald-500/30 bg-[#0B1A13] p-5 sm:p-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-emerald-400">
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
              Diagnostic Complete
            </div>
            <h2 className="mt-2 font-display text-2xl font-extrabold text-[#F8FAFC] sm:text-3xl">
              Surfaced <span className="text-emerald-400">{total} High-Impact Interventions</span>
            </h2>
            <p className="mt-1 text-xs text-[#94A3B8]">
              Grounded in current store records. Each intervention includes verified impact modeling.
            </p>
          </div>

          {GROUPS.map((g) => {
            const items = insights[g.key] || [];
            if (!items.length) return null;
            return (
              <div key={g.key} className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <g.icon size={16} className={g.color} />
                    <h3 className="font-display text-base font-bold text-[#F8FAFC]">{g.label}</h3>
                    <span className="rounded border border-[#16221B] bg-[#070C0A] px-2 py-0.5 text-xs text-[#94A3B8]">
                      {items.length}
                    </span>
                  </div>
                </div>
                <div className="grid gap-4 lg:grid-cols-2">
                  {items.map((ins) => (
                    <InsightCard
                      key={ins.id}
                      insight={ins}
                      currency={cur}
                      category={g.label}
                      onAsk={(i) => openAsk(`Analyze this finding and provide actionable mitigation: ${i.title}`)}
                      onAction={onAction}
                    />
                  ))}
                </div>
              </div>
            );
          })}

          <div className="flex justify-center pt-2">
            <Button
              variant="ghost"
              onClick={() => setRevealed(false)}
              className="text-xs text-[#64748B] hover:bg-[#0B110E] hover:text-[#F8FAFC]"
              data-testid="rescan-btn"
            >
              Re-run diagnostic scan
            </Button>
          </div>
        </>
      )}
    </div>
  );
}

