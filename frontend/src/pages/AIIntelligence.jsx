import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  BrainCircuit, Radar, Check, Loader2, TrendingDown, TrendingUp,
  ShieldAlert, Users, Boxes, ArrowRight, Wallet,
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
  { key: "customer_issues", label: "Customer Issues", icon: Users, color: "text-cyan-400" },
  { key: "inventory_risks", label: "Inventory Risks", icon: Boxes, color: "text-purple-400" },
];

function ScanSequence({ onDone }) {
  const [phase, setPhase] = useState("connecting"); // connecting -> analyzing
  const [checked, setChecked] = useState(0);

  useEffect(() => {
    if (phase === "connecting") {
      if (checked < DATASETS.length) {
        const t = setTimeout(() => setChecked((c) => c + 1), 260);
        return () => clearTimeout(t);
      }
      const t = setTimeout(() => setPhase("analyzing"), 400);
      return () => clearTimeout(t);
    }
    if (phase === "analyzing") {
      const t = setTimeout(onDone, 1800);
      return () => clearTimeout(t);
    }
  }, [phase, checked, onDone]);

  return (
    <div className="flex flex-col items-center py-12 text-center" data-testid="xray-scanning">
      <div className="relative mb-8 flex h-32 w-32 items-center justify-center">
        <span className="absolute h-full w-full rounded-full border border-emerald-500/40 animate-radar" />
        <span className="absolute h-2/3 w-2/3 rounded-full border border-cyan-500/40 animate-radar" style={{ animationDelay: "0.6s" }} />
        <div className="absolute h-24 w-24 overflow-hidden rounded-full">
          <div className="h-full w-full animate-sweep" style={{ background: "conic-gradient(from 0deg, transparent 0deg, rgba(16,185,129,0.35) 60deg, transparent 120deg)" }} />
        </div>
        <span className="relative z-10 flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-500/15 text-emerald-400">
          <Radar size={26} />
        </span>
      </div>

      {phase === "connecting" ? (
        <>
          <h2 className="font-display text-lg font-bold text-[#F8FAFC]">Connecting business data</h2>
          <div className="mt-5 grid w-full max-w-md grid-cols-2 gap-2 sm:grid-cols-4">
            {DATASETS.map((d, i) => (
              <div
                key={d}
                className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-xs font-medium transition-all ${
                  i < checked ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-200" : "border-[#1E2235] bg-[#0F111A] text-[#64748B]"
                }`}
              >
                {i < checked ? <Check size={13} className="text-emerald-400" /> : <Loader2 size={13} className="animate-spin" />}
                {d}
              </div>
            ))}
          </div>
        </>
      ) : (
        <>
          <h2 className="font-display text-lg font-bold text-[#F8FAFC]">Analyzing your business…</h2>
          <p className="mt-2 text-sm text-[#94A3B8]">Correlating profit, demand, returns and marketing signals</p>
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
    <div className="space-y-8">
      <SectionHeader
        title="AI Intelligence"
        subtitle="Business X-Ray · a full-body scan of your commerce operation"
        icon={BrainCircuit}
        right={
          <Button
            onClick={() => navigate("/app/profit")}
            variant="outline"
            className="border-[#2D334B] bg-transparent text-[#94A3B8] hover:bg-[#161926] hover:text-[#F8FAFC]"
            data-testid="open-profit-btn"
          >
            <Wallet size={15} className="mr-1.5" /> True Profit Engine
          </Button>
        }
      />

      {!revealed && (
        <Card className="relative overflow-hidden p-6">
          <div
            className="pointer-events-none absolute inset-0 opacity-50"
            style={{ background: "radial-gradient(500px circle at 50% 0%, rgba(16,185,129,0.1), transparent 60%)" }}
          />
          {scanning ? (
            <ScanSequence onDone={() => { setScanning(false); setRevealed(true); }} />
          ) : (
            <div className="relative flex flex-col items-center py-10 text-center">
              <span className="mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-500/15 text-emerald-400">
                <Radar size={30} />
              </span>
              <h2 className="font-display text-2xl font-bold text-[#F8FAFC]">Scan My Business</h2>
              <p className="mt-2 max-w-md text-sm text-[#94A3B8]">
                AHONIX will analyze 8 connected datasets and surface money leaks, growth opportunities and risks —
                each with evidence, reasoning and projected impact.
              </p>
              <Button
                onClick={() => setScanning(true)}
                className="mt-6 bg-emerald-500 px-6 font-semibold text-emerald-950 hover:bg-emerald-400"
                data-testid="business-xray-scan-btn"
              >
                <Radar size={16} className="mr-2" /> Start scan
              </Button>
            </div>
          )}
        </Card>
      )}

      {revealed && (
        <>
          <div className="animate-fade-up rounded-2xl border border-emerald-500/30 bg-gradient-to-r from-emerald-500/10 to-transparent p-6">
            <h2 className="font-display text-3xl font-extrabold text-[#F8FAFC]">
              We found <span className="text-emerald-400">{total} opportunities</span>
            </h2>
            <p className="mt-1 text-sm text-[#94A3B8]">
              Organized by impact area. Figures are estimated or projected from demo data.
            </p>
          </div>

          {GROUPS.map((g) => {
            const items = insights[g.key] || [];
            if (!items.length) return null;
            return (
              <div key={g.key}>
                <div className="mb-3 flex items-center gap-2">
                  <g.icon size={17} className={g.color} />
                  <h3 className="font-display text-base font-bold text-[#F8FAFC]">{g.label}</h3>
                  <span className="rounded bg-[#161926] px-1.5 py-0.5 text-xs text-[#94A3B8]">{items.length}</span>
                </div>
                <div className="grid gap-4 lg:grid-cols-2">
                  {items.map((ins) => (
                    <InsightCard
                      key={ins.id}
                      insight={ins}
                      currency={cur}
                      category={g.label}
                      onAsk={(i) => openAsk(`Explain this finding: ${i.title}`)}
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
              className="text-[#64748B] hover:bg-[#161926] hover:text-[#F8FAFC]"
              data-testid="rescan-btn"
            >
              Run scan again
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
