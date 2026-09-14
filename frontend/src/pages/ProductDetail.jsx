import React from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Sparkles } from "lucide-react";
import { useSection } from "@/lib/hooks";
import { useUI } from "@/context/UIContext";
import { PageSkeleton, ErrorState } from "@/components/StateViews";
import { EmptyWorkspace } from "@/pages/Overview";
import { HealthRing } from "@/pages/Products";
import { Card, SectionHeader, Stat } from "@/components/primitives";
import { ValueBadge } from "@/components/ValueBadge";
import { BarSeries } from "@/components/charts";
import { fmtCurrency, fmtNumber } from "@/lib/api";
import { Button } from "@/components/ui/button";

const DIMS = [
  ["demand", "Demand"], ["profitability", "Profitability"], ["returns", "Returns"],
  ["inventory", "Inventory"], ["marketing", "Marketing"],
];

export default function ProductDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { openAsk } = useUI();
  const { data, isLoading, isError, refetch } = useSection(`product-${id}`, `/products/${id}`);
  if (isLoading) return <PageSkeleton />;
  if (isError) return <ErrorState onRetry={refetch} />;
  if (data?.empty) return <EmptyWorkspace name={data.workspace?.name} />;

  const cur = data.workspace.currency;
  const p = data.product;
  const weekly = p.weekly.map((v, i) => ({ week: `W${i + 1}`, revenue: v }));

  return (
    <div className="space-y-8">
      <button onClick={() => navigate("/app/products")} className="flex items-center gap-1.5 text-sm text-[#94A3B8] hover:text-[#F8FAFC]" data-testid="product-back">
        <ArrowLeft size={15} /> All products
      </button>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-center gap-4">
          <HealthRing score={p.health.score} size={64} />
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="font-display text-2xl font-extrabold text-[#F8FAFC]">{p.name}</h1>
              {p.cogs_status && <ValueBadge kind={p.cogs_status} />}
            </div>
            <p className="text-sm text-[#64748B]">{p.category} · {p.channel} · Health score {p.health.score}/100</p>
          </div>
        </div>
        <Button onClick={() => openAsk(`How can I improve ${p.name}?`)} className="bg-emerald-500 font-semibold text-emerald-950 hover:bg-emerald-400">
          <Sparkles size={15} className="mr-1.5" /> Ask AHONIX
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        <Card className="p-5"><Stat label="Units sold" value={fmtNumber(p.units)} /></Card>
        <Card className="p-5"><Stat label="Revenue" value={fmtCurrency(p.revenue, cur)} /></Card>
        <Card className="p-5">
          <Stat
            label="Unit Cost (COGS)"
            value={fmtCurrency(p.unit_cost || 0, cur)}
            sub={p.cogs_status ? `Source: ${p.cogs_status}` : undefined}
          />
        </Card>
        <Card className="p-5"><Stat label="True profit" value={fmtCurrency(p.true_profit, cur)} sub={`${p.margin}% margin`} /></Card>
        <Card className="p-5"><Stat label="Return rate" value={`${p.return_rate}%`} /></Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="p-5 lg:col-span-2">
          <SectionHeader title="Revenue trend" subtitle="Weekly · last 12 weeks" />
          <div className="mt-4"><BarSeries data={weekly} dataKey="revenue" xKey="week" currency={cur} /></div>
        </Card>
        <Card className="p-5">
          <SectionHeader title="Health breakdown" />
          <div className="mt-4 space-y-3">
            {DIMS.map(([k, label]) => {
              const v = p.health.breakdown[k];
              const color = v >= 70 ? "#10B981" : v >= 45 ? "#F59E0B" : "#F43F5E";
              return (
                <div key={k}>
                  <div className="mb-1 flex justify-between text-xs">
                    <span className="text-[#CBD5E1]">{label}</span>
                    <span className="font-metric font-semibold" style={{ color }}>{v}</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-[#0F111A]">
                    <div className="h-full rounded-full" style={{ width: `${v}%`, background: color }} />
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      </div>

      <Card className="border-l-4 border-l-emerald-500 bg-emerald-950/10 p-5">
        <div className="flex items-start gap-3">
          <Sparkles size={17} className="mt-0.5 text-emerald-400" />
          <div>
            <h3 className="font-display text-sm font-bold text-[#F8FAFC]">AHONIX recommendation</h3>
            <p className="mt-1 text-sm text-[#94A3B8]">
              {p.margin > 20
                ? `Strong margin at ${p.margin}%. With ${fmtCurrency(p.ad_spend, cur)} of ad spend over 12 weeks, there's room to scale acquisition profitably.`
                : p.return_rate > 12
                ? `Return rate of ${p.return_rate}% is eroding margin. Improve product images and sizing guidance to protect profit.`
                : `Solid performer. Maintain inventory cover and monitor marketing efficiency to keep the health score high.`}
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
}
