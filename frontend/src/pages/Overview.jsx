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

export function EmptyWorkspace({
  name,
  title = "No commerce data yet",
  description,
  actionLabel = "Go to integrations",
  actionPath = "/app/settings",
}) {
  const navigate = useNavigate();
  return (
    <EmptyState
      title={title}
      description={
        description ||
        `${name || "This workspace"} has no commerce data connected yet. Connect Shopify or add your first data source in Settings to activate this view.`
      }
      action={
        <Button
          onClick={() => navigate(actionPath)}
          className="bg-emerald-500 font-semibold text-emerald-950 hover:bg-emerald-400"
          data-testid="connect-data-btn"
        >
          {actionLabel} <ArrowRight size={15} className="ml-1.5" />
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

  const isDemo = Boolean(data?.workspace?.is_demo);
  const cur = data?.workspace?.currency || "USD";
  const b = data?.briefing || {};
  const kpis = data?.kpis || [];
  const weekly = data?.weekly || [];
  const priorities = data?.priorities || [];

  // Check if live workspace has any telemetry yet
  const hasCommerceData =
    isDemo ||
    Boolean(b?.yesterday) ||
    kpis.some((k) => k.value > 0) ||
    weekly.length > 0;

  if (!hasCommerceData) {
    return (
      <div className="space-y-8" data-testid="overview-empty-state">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-emerald-400">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(0,229,153,0.8)]" />
              Executive Command Center
            </div>
            <h1 className="mt-1.5 font-display text-3xl font-extrabold tracking-tight text-[#F8FAFC] sm:text-4xl">
              {greeting()}, {(user?.name || "Alex").split(" ")[0]}
            </h1>
            <p className="mt-1 text-xs text-[#94A3B8]">
              {data?.workspace?.name || "Your Workspace"} · Live Production Mode
            </p>
          </div>
        </div>

        <EmptyWorkspace
          name={data?.workspace?.name}
          title="No commerce data yet"
          description="Connect Shopify, Meta Ads, Google Ads, or Stripe in Settings to activate real-time telemetry and executive insights."
        />
      </div>
    );
  }

  const onAction = (insight) => {
    if (["Approve", "Simulate", "Apply"].includes(insight.action)) navigate("/app/action-center");
    else if (insight.id?.includes("de")) navigate("/app/markets");
    else navigate("/app/ai-intelligence");
  };

  return (
    <div className="space-y-8" data-testid="overview-page">
      {/* Header */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-emerald-400">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(0,229,153,0.8)]" />
            Executive Command Center
          </div>
          <h1 className="mt-1.5 font-display text-3xl font-extrabold tracking-tight text-[#F8FAFC] sm:text-4xl">
            {greeting()}, {(user?.name || "Alex").split(" ")[0]}
          </h1>
          <p className="mt-1 text-xs text-[#94A3B8]">
            Real-time merchant operating telemetry and prioritized profit opportunities.
          </p>
        </div>
        {data?.workspace?.is_demo && <DemoRibbon storeName={data.workspace.name} />}
      </div>

      {/* Executive Daily Briefing */}
      <div className="rounded-xl border border-[#16221B] bg-[#0B110E] overflow-hidden shadow-sm">
        <div className="border-b border-[#16221B] bg-[#070C0A] p-5 sm:p-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg border border-emerald-500/20 bg-emerald-500/10 text-emerald-400">
                <Bell size={14} />
              </span>
              <h2 className="font-display text-sm font-bold uppercase tracking-wider text-[#F8FAFC]">
                Daily Commerce Briefing
              </h2>
            </div>
            <ValueBadge kind="ACTUAL" />
          </div>
          <p className="mt-1 text-xs text-[#64748B]">Prior 24-hour financial & operational performance snapshot</p>

          <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            {[
              ["Net Revenue", fmtCurrency(b?.yesterday?.revenue ?? 0, cur)],
              ["True Profit", fmtCurrency(b?.yesterday?.true_profit ?? 0, cur)],
              ["Orders", fmtNumber(b?.yesterday?.orders ?? 0)],
              ["Return Rate", fmtPercent(b?.yesterday?.return_rate ?? 0)],
              [
                "Marketing Efficiency",
                b?.yesterday?.marketing_eff && b.yesterday.marketing_eff > 0
                  ? `${b.yesterday.marketing_eff}x`
                  : "—",
              ],
            ].map(([l, v], idx) => (
              <div
                key={l}
                className={`rounded-lg border border-[#16221B] bg-[#0B110E] p-3 ${
                  idx === 4 ? "col-span-2 sm:col-span-1" : ""
                }`}
              >
                <p className="text-[11px] uppercase tracking-wider text-[#64748B]">{l}</p>
                <p className="mt-1 font-metric text-lg font-bold text-[#F8FAFC]">{v}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="grid gap-6 p-5 sm:p-6 md:grid-cols-2">
          <div>
            <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-[#94A3B8]">
              Operating Observations
            </p>
            <ul className="space-y-2.5">
              {(b?.noticed || []).map((n, i) => (
                <li key={i} className="flex items-start gap-2.5 text-xs leading-relaxed text-[#CBD5E1]">
                  <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-400" />
                  <span>{n}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded-xl border border-emerald-500/20 bg-[#070C0A] p-4 sm:p-5">
            <div className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
              <p className="text-xs font-semibold uppercase tracking-wider text-emerald-400">
                Primary Recommendation
              </p>
            </div>
            <p className="mt-2 font-display text-base font-bold text-[#F8FAFC]">
              {b?.recommendation?.title || "Connect Data Sources"}
            </p>
            <p className="mt-1.5 text-xs leading-relaxed text-[#94A3B8]">
              {b?.recommendation?.recommendation || "Integrate your sales channels to surface automated operating recommendations."}
            </p>
            <Button
              size="sm"
              onClick={() => navigate("/app/action-center")}
              className="mt-4 h-8 bg-emerald-500 font-semibold text-emerald-950 hover:bg-emerald-400"
              data-testid="briefing-action-btn"
            >
              Review in Action Center <ArrowRight size={13} className="ml-1.5" />
            </Button>
          </div>
        </div>
      </div>

      {/* Core KPIs */}
      {kpis.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {kpis.map((k) => (
            <KpiCard
              key={k.id || k.label}
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
      )}

      {/* Revenue Trend */}
      <Card className="p-5 sm:p-6">
        <SectionHeader
          title="Revenue & Growth Trajectory"
          subtitle="12-week store sales velocity across all connected channels"
          right={<ValueBadge kind="ACTUAL" />}
        />
        <div className="mt-5">
          <TrendArea data={weekly} dataKey="revenue" currency={cur} />
        </div>
      </Card>

      {/* Strategic Priorities */}
      {priorities.length > 0 && (
        <div>
          <SectionHeader
            title="Strategic Priorities"
            subtitle={`${priorities.length} high-impact interventions surfaced by your data`}
            right={
              <Button
                variant="outline"
                onClick={() => navigate("/app/ai-intelligence")}
                className="border-[#16221B] bg-[#0B110E] text-xs text-[#94A3B8] hover:border-emerald-500/30 hover:bg-[#0E1713] hover:text-[#F8FAFC]"
                data-testid="view-xray-btn"
              >
                Diagnostic Intelligence <ArrowRight size={13} className="ml-1.5" />
              </Button>
            }
          />
          <div className="mt-5 grid gap-4 lg:grid-cols-3">
            {priorities.map((p) => (
              <InsightCard
                key={p.id}
                insight={p}
                category={p.category}
                currency={cur}
                onAsk={(ins) => openAsk(`Analyze this finding and provide step-by-step guidance: ${ins.title}`)}
                onAction={onAction}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

