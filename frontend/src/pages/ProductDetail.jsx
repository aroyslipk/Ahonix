import React from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, MessageSquare, Compass } from "lucide-react";
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
  ["demand", "Demand Velocity"], ["profitability", "Margin Efficiency"], ["returns", "Return Resistance"],
  ["inventory", "Stock Cover"], ["marketing", "Channel Traction"],
];

export default function ProductDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { openAsk } = useUI();
  const { data, isLoading, isError, refetch } = useSection(`product-${id}`, `/products/${id}`);
  if (isLoading) return <PageSkeleton />;
  if (isError) return <ErrorState onRetry={refetch} />;
  if (data?.empty) return <EmptyWorkspace name={data.workspace?.name} />;

  const cur = data?.workspace?.currency || "USD";
  const p = data?.product;

  if (!p) {
    return (
      <div className="space-y-6">
        <button
          onClick={() => navigate("/app/products")}
          className="flex items-center gap-1.5 text-xs text-[#94A3B8] hover:text-[#F8FAFC] transition-colors"
          data-testid="product-back"
        >
          <ArrowLeft size={14} /> Return to catalog overview
        </button>
        <EmptyWorkspace
          name={data?.workspace?.name}
          title="Product not found"
          description="This SKU does not exist in the active catalog or has not been synced yet."
          actionLabel="View Catalog"
          actionPath="/app/products"
        />
      </div>
    );
  }

  const weekly = (p.weekly || []).map((v, i) => ({ week: `W${i + 1}`, revenue: v }));

  return (
    <div className="space-y-8" data-testid="product-detail-page">
      <button onClick={() => navigate("/app/products")} className="flex items-center gap-1.5 text-xs text-[#94A3B8] hover:text-[#F8FAFC] transition-colors" data-testid="product-back">
        <ArrowLeft size={14} /> Return to catalog overview
      </button>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-center gap-4">
          <HealthRing score={p.health?.score ?? 50} size={64} />
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="font-display text-2xl font-bold text-[#F8FAFC]">{p.name || "Untitled Product"}</h1>
              {p.cogs_status && <ValueBadge kind={p.cogs_status} />}
            </div>
            <p className="mt-1 text-xs text-[#64748B]">{p.category || "General"} · {p.channel || "Direct"} · Health Index {p.health?.score ?? 50}/100</p>
          </div>
        </div>
        <Button onClick={() => openAsk(`Analyze unit economics and profit levers for ${p.name || "this product"}`)} className="bg-emerald-500 font-semibold text-emerald-950 hover:bg-emerald-400 text-xs">
          <MessageSquare size={13} className="mr-1.5" /> Ask AHONIX
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:gap-4 sm:grid-cols-3 lg:grid-cols-5">
        <Card className="p-4 sm:p-5"><Stat label="Units sold" value={fmtNumber(p.units || 0)} /></Card>
        <Card className="p-4 sm:p-5"><Stat label="Gross revenue" value={fmtCurrency(p.revenue || 0, cur)} /></Card>
        <Card className="p-4 sm:p-5">
          <Stat
            label="Unit COGS"
            value={fmtCurrency(p.unit_cost || 0, cur)}
            sub={p.cogs_status ? `Source: ${p.cogs_status}` : undefined}
          />
        </Card>
        <Card className="p-4 sm:p-5"><Stat label="True net profit" value={fmtCurrency(p.true_profit || 0, cur)} sub={`${p.margin || 0}% margin`} /></Card>
        <Card className="col-span-2 sm:col-span-1 p-4 sm:p-5"><Stat label="Return rate" value={`${p.return_rate || 0}%`} /></Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="p-5 sm:p-6 lg:col-span-2">
          <SectionHeader title="Revenue Trajectory" subtitle="12-week store sales velocity for this SKU" />
          <div className="mt-5"><BarSeries data={weekly} dataKey="revenue" xKey="week" currency={cur} /></div>
        </Card>
        <Card className="p-5 sm:p-6">
          <SectionHeader title="Multidimensional Health" subtitle="Audited performance pillars" />
          <div className="mt-5 space-y-3.5">
            {DIMS.map(([k, label]) => {
              const v = p.health?.breakdown?.[k] ?? 50;
              const color = v >= 70 ? "#00E599" : v >= 45 ? "#F59E0B" : "#F43F5E";
              return (
                <div key={k}>
                  <div className="mb-1.5 flex justify-between text-xs">
                    <span className="text-[#CBD5E1]">{label}</span>
                    <span className="font-metric font-bold" style={{ color }}>{v}/100</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-[#070C0A] border border-[#16221B]">
                    <div className="h-full rounded-full" style={{ width: `${v}%`, background: color }} />
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      </div>

      <div className="rounded-xl border border-emerald-500/30 bg-[#0B1A13] p-5">
        <div className="flex items-start gap-3">
          <Compass size={18} className="mt-0.5 shrink-0 text-emerald-400" />
          <div>
            <h3 className="font-display text-sm font-bold text-[#F8FAFC]">Autonomous Merchant Recommendation</h3>
            <p className="mt-1 text-xs leading-relaxed text-[#CBD5E1]">
              {p.margin > 20
                ? `Strong unit margin at ${p.margin}%. With ${fmtCurrency(p.ad_spend, cur)} of ad spend over 12 weeks, there's verifiable headroom to scale acquisition profitably.`
                : p.return_rate > 12
                ? `Return rate of ${p.return_rate}% is actively eroding profit margin. Improve specification clarity and sizing guidance to protect net revenue.`
                : `Solid baseline performer. Maintain inventory replenishment rhythm and monitor marketing efficiency to sustain high health index.`}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

