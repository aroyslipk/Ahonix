import React from "react";
import { Users } from "lucide-react";
import { useSection } from "@/lib/hooks";
import { PageSkeleton, ErrorState } from "@/components/StateViews";
import { EmptyWorkspace } from "@/pages/Overview";
import { Card, SectionHeader, Stat } from "@/components/primitives";
import { Donut, DONUT_COLORS } from "@/components/charts";
import { fmtCurrency, fmtNumber } from "@/lib/api";

export default function Customers() {
  const { data, isLoading, isError, refetch } = useSection("customers", "/customers");
  if (isLoading) return <PageSkeleton />;
  if (isError) return <ErrorState onRetry={refetch} />;
  if (data?.empty) return <EmptyWorkspace name={data.workspace?.name} />;

  const cur = data.workspace.currency;
  const c = data.customers;

  return (
    <div className="space-y-8">
      <SectionHeader title="Customers & LTV" subtitle="Segments, lifetime value and retention signals" icon={Users} />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Card className="p-5"><Stat label="Total Customers" value={fmtNumber(c.total)} /></Card>
        <Card className="p-5"><Stat label="Repeat Rate" value={`${c.repeat_rate}%`} sub={`${fmtNumber(c.repeat)} repeat`} /></Card>
        <Card className="p-5"><Stat label="Avg LTV" value={fmtCurrency(c.avg_ltv, cur)} /></Card>
        <Card className="p-5"><Stat label="Purchase Frequency" value={`${c.purchase_frequency}x`} /></Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="p-5 lg:col-span-2">
          <SectionHeader title="Customer segments" subtitle="RFM-style segmentation" />
          <div className="mt-4 space-y-3">
            {c.segments.map((s, i) => (
              <div key={s.name} className="flex items-center gap-4">
                <div className="w-24 shrink-0 text-sm font-medium text-[#CBD5E1]">{s.name}</div>
                <div className="flex-1">
                  <div className="h-6 overflow-hidden rounded-md bg-[#0F111A]">
                    <div className="flex h-full items-center rounded-md px-2 text-[10px] font-semibold text-black/70"
                      style={{ width: `${s.share * 2.6}%`, background: DONUT_COLORS[i % DONUT_COLORS.length] }}>
                      {s.share}%
                    </div>
                  </div>
                </div>
                <div className="w-20 shrink-0 text-right font-metric text-xs text-[#94A3B8]">LTV {fmtCurrency(s.ltv, cur, true)}</div>
                <div className="w-16 shrink-0 text-right text-xs text-[#64748B]">{s.return_rate}% ret</div>
              </div>
            ))}
          </div>
        </Card>

        <Card className="p-5">
          <SectionHeader title="By country" />
          <div className="mt-4"><Donut data={c.by_country} dataKey="share" /></div>
          <div className="mt-3 space-y-1.5">
            {c.by_country.map((x, i) => (
              <div key={x.country} className="flex items-center justify-between text-sm">
                <span className="flex items-center gap-2 text-[#CBD5E1]">
                  <span className="h-2 w-2 rounded-full" style={{ background: DONUT_COLORS[i % DONUT_COLORS.length] }} />
                  {x.flag} {x.country}
                </span>
                <span className="font-metric text-[#94A3B8]">{x.share}%</span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {[
          { t: "High-value customers", d: `Champions & Loyal drive ${c.segments[0].share + c.segments[1].share}% with the highest LTV. Reward and retain them.`, cls: "border-l-emerald-500" },
          { t: "Churn risk", d: `${c.segments[3].share}% sit in At-Risk with elevated returns (${c.segments[3].return_rate}%). Trigger a win-back flow.`, cls: "border-l-amber-500" },
          { t: "Repeat opportunity", d: `Repeat rate is ${c.repeat_rate}%. A post-purchase flow could lift frequency above ${c.purchase_frequency}x.`, cls: "border-l-cyan-500" },
        ].map((x) => (
          <Card key={x.t} className={`border-l-4 p-5 ${x.cls}`}>
            <h3 className="font-display text-sm font-bold text-[#F8FAFC]">{x.t}</h3>
            <p className="mt-1.5 text-sm text-[#94A3B8]">{x.d}</p>
          </Card>
        ))}
      </div>
    </div>
  );
}
