import React from "react";
import { useNavigate } from "react-router-dom";
import { Sun, ArrowRight, Sparkles, Bell, Wallet } from "lucide-react";
import { useSection } from "@/lib/hooks";
import { useUI } from "@/context/UIContext";
import { PageSkeleton, ErrorState, EmptyState } from "@/components/StateViews";
import { KpiCard } from "@/components/KpiCard";
import { InsightCard } from "@/components/InsightCard";
import { Card, SectionHeader, DemoRibbon } from "@/components/primitives";
import { TrendArea } from "@/components/charts";
import { fmtCurrency, fmtNumber, fmtPercent } from "@/lib/api";
import { ValueBadge } from "@/components/ValueBadge";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/context/AuthContext";

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

export function EmptyWorkspace({ name }) {
  const navigate = useNavigate();
  return (
    <EmptyState
      title="Connect your commerce data"
      description={`${name} has no data connected yet. Add an integration to start seeing insights, or switch to the demo workspace to explore AHONIX now.`}
      action={
        <Button onClick={() => navigate("/app/settings")} className="bg-emerald-500 font-semibold text-emerald-950 hover:bg-emerald-400" data-testid="connect-data-btn">
          Go to integrations <ArrowRight size={15} className="ml-1.5" />
        </Button>
      }
    />
  );
}

export default function Overview() {
  const { user } = useAuth();
  const { openAsk } = useUI();
  const navigate = useNavigate();
  const { data, isLoading, isError, refetch } = useSection("overview", "/overview");

  if (isLoading) return <PageSkeleton />;
  if (isError) return <ErrorState onRetry={refetch} />;
  if (data?.empty) return <EmptyWorkspace name={data.workspace?.name} />;

  const cur = data.workspace.currency;
  const b = data.briefing;

  const onAction = (insight) => {
    if (["Approve", "Simulate", "Apply"].includes(insight.action)) navigate("/app/action-center");
    else if (insight.id?.includes("de")) navigate("/app/markets");
    else navigate("/app/ai-intelligence");
  };

  return (
    <div className="space-y-8">
      {/* header */}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-emerald-400">
            <Sun size={18} />
            <span className="text-xs font-medium uppercase tracking-wide">Command Center</span>
          </div>
          <h1 className="mt-1 font-display text-3xl font-extrabold tracking-tight text-[#F8FAFC] sm:text-4xl">
            {greeting()}, {(user?.name || "Alex").split(" ")[0]} 👋
          </h1>
          <p className="mt-1 text-[#94A3B8]">Here's what matters in your business today.</p>
        </div>
        {data.workspace.is_demo && <DemoRibbon storeName={data.workspace.name} />}
      </div>

      {/* daily briefing */}
      <Card className="overflow-hidden">
        <div className="border-b border-[#1E2235] bg-gradient-to-r from-emerald-500/5 to-transparent p-5">
          <div className="flex items-center gap-2">
            <Bell size={15} className="text-emerald-400" />
            <h2 className="font-display text-sm font-bold uppercase tracking-wide text-[#F8FAFC]">Daily AI Briefing</h2>
            <ValueBadge kind="DEMO" className="ml-1" />
          </div>
          <p className="mt-1 text-xs text-[#64748B]">Yesterday's snapshot</p>
          <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-5">
            {[
              ["Revenue", fmtCurrency(b.yesterday.revenue, cur)],
              ["True Profit", fmtCurrency(b.yesterday.true_profit, cur)],
              ["Orders", fmtNumber(b.yesterday.orders)],
              ["Return Rate", fmtPercent(b.yesterday.return_rate)],
              [
                "Mkt Efficiency",
                b.yesterday.marketing_eff && b.yesterday.marketing_eff > 0
                  ? `${b.yesterday.marketing_eff}x`
                  : "—",
              ],
            ].map(([l, v]) => (
              <div key={l}>
                <p className="text-xs text-[#64748B]">{l}</p>
                <p className="mt-0.5 font-metric text-lg font-bold text-[#F8FAFC]">{v}</p>
              </div>
            ))}
          </div>
        </div>
        <div className="grid gap-5 p-5 md:grid-cols-2">
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-[#94A3B8]">AHONIX noticed</p>
            <ul className="space-y-2">
              {b.noticed.map((n, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-[#CBD5E1]">
                  <Sparkles size={13} className="mt-1 shrink-0 text-emerald-400" /> {n}
                </li>
              ))}
            </ul>
          </div>
          <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4">
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-emerald-300">My recommendation</p>
            <p className="font-display text-sm font-bold text-[#F8FAFC]">{b.recommendation.title}</p>
            <p className="mt-1 text-sm text-[#94A3B8]">{b.recommendation.recommendation}</p>
            <Button
              size="sm"
              onClick={() => navigate("/app/action-center")}
              className="mt-3 h-8 bg-emerald-500 text-emerald-950 hover:bg-emerald-400"
              data-testid="briefing-action-btn"
            >
              Review action <ArrowRight size={13} className="ml-1" />
            </Button>
          </div>
        </div>
      </Card>

      {/* KPIs */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
        {data.kpis.map((k) => (
          <KpiCard
            key={k.id}
            kpi={k}
            currency={cur}
            onClick={
              k.id === "true-profit"
                ? () => navigate("/app/profit")
                : k.id === "marketing-eff"
                ? () => navigate("/app/marketing")
                : undefined
            }
          />
        ))}
      </div>

      {/* revenue trend */}
      <Card className="p-5">
        <SectionHeader
          title="Revenue trend"
          subtitle="Weekly revenue · last 12 weeks"
          right={<ValueBadge kind="ACTUAL" />}
        />
        <div className="mt-4">
          <TrendArea data={data.weekly} dataKey="revenue" currency={cur} />
        </div>
      </Card>

      {/* AI priorities */}
      <div>
        <SectionHeader
          title="AI Priorities"
          subtitle={`${data.priorities.length} things need your attention`}
          icon={Sparkles}
          right={
            <Button
              variant="outline"
              onClick={() => navigate("/app/ai-intelligence")}
              className="border-[#2D334B] bg-transparent text-[#94A3B8] hover:bg-[#161926] hover:text-[#F8FAFC]"
              data-testid="view-xray-btn"
            >
              Open Business X-Ray <ArrowRight size={15} className="ml-1.5" />
            </Button>
          }
        />
        <div className="mt-4 grid gap-4 lg:grid-cols-3">
          {data.priorities.map((p) => (
            <InsightCard
              key={p.id}
              insight={p}
              category={p.category}
              currency={cur}
              onAsk={(ins) => openAsk(`Explain this: ${ins.title}`)}
              onAction={onAction}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
