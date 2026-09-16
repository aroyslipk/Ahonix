import React from "react";
import { Users, TrendingUp, AlertTriangle, RefreshCw } from "lucide-react";
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
    <div className="space-y-8" data-testid="customers-page">
      <SectionHeader
        title="Customer Intelligence & LTV"
        subtitle="Cohort retention, lifetime value distribution, and churn vulnerability analysis"
        icon={Users}
      />

      <div className="grid grid-cols-1 gap-3 sm:gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="p-4 sm:p-5"><Stat label="Unique Customers" value={fmtNumber(c.total)} /></Card>
        <Card className="p-4 sm:p-5"><Stat label="Repeat Purchase Rate" value={`${c.repeat_rate}%`} sub={`${fmtNumber(c.repeat)} multi-order profiles`} /></Card>
        <Card className="p-4 sm:p-5"><Stat label="Blended LTV" value={fmtCurrency(c.avg_ltv, cur)} /></Card>
        <Card className="p-4 sm:p-5"><Stat label="Order Frequency" value={`${c.purchase_frequency}x`} sub="Annual velocity" /></Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="p-5 sm:p-6 lg:col-span-2">
          <SectionHeader title="RFM Segment Matrix" subtitle="Behavioral clustering by recency, frequency and monetary value" />
          <div className="mt-5 overflow-x-auto">
            <div className="min-w-[420px] space-y-3.5">
              {c.segments.map((s, i) => (
                <div key={s.name} className="flex items-center gap-4">
                  <div className="w-28 shrink-0 text-xs font-semibold text-[#CBD5E1]">{s.name}</div>
                  <div className="flex-1">
                    <div className="h-5 overflow-hidden rounded bg-[#070C0A] border border-[#16221B]">
                      <div
                        className="flex h-full items-center rounded px-2 text-[10px] font-bold text-black"
                        style={{ width: `${s.share * 2.6}%`, background: DONUT_COLORS[i % DONUT_COLORS.length] }}
                      >
                        {s.share}%
                      </div>
                    </div>
                  </div>
                  <div className="w-24 shrink-0 text-right font-metric text-xs font-semibold text-[#CBD5E1]">LTV {fmtCurrency(s.ltv, cur, true)}</div>
                  <div className="w-20 shrink-0 text-right font-metric text-xs text-[#64748B]">{s.return_rate}% ret</div>
                </div>
              ))}
            </div>
          </div>
        </Card>

        <Card className="p-5 sm:p-6">
          <SectionHeader title="Regional Distribution" subtitle="Customer concentration by country" />
          <div className="mt-5"><Donut data={c.by_country} dataKey="share" /></div>
          <div className="mt-4 space-y-2">
            {c.by_country.map((x, i) => (
              <div key={x.country} className="flex items-center justify-between text-xs">
                <span className="flex items-center gap-2 text-[#CBD5E1]">
                  <span className="h-2 w-2 rounded-full" style={{ background: DONUT_COLORS[i % DONUT_COLORS.length] }} />
                  <span>{x.flag}</span>
                  <span>{x.country}</span>
                </span>
                <span className="font-metric font-semibold text-[#94A3B8]">{x.share}%</span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {[
          { t: "High-Conviction Retention", d: `Champions & Loyal cohorts drive ${c.segments[0].share + c.segments[1].share}% of sales with maximal LTV. Protect their margin contribution.`, icon: TrendingUp, cls: "border-l-emerald-500 bg-[#0B1A13]" },
          { t: "Friction & Churn Risk", d: `${c.segments[3].share}% of profiles are At-Risk with elevated return rates (${c.segments[3].return_rate}%). Initiate proactive resolution.`, icon: AlertTriangle, cls: "border-l-amber-500 bg-[#0B110E]" },
          { t: "Expansion Potential", d: `Repeat purchase rate is ${c.repeat_rate}%. Automated replenishment flows could lift frequency beyond ${c.purchase_frequency}x.`, icon: RefreshCw, cls: "border-l-sky-500 bg-[#0B110E]" },
        ].map((x) => (
          <div key={x.t} className={`rounded-xl border border-[#16221B] border-l-4 p-5 transition-all duration-150 ${x.cls}`}>
            <div className="flex items-center gap-2">
              <x.icon size={15} className="text-emerald-400" />
              <h3 className="font-display text-xs font-bold uppercase tracking-wider text-[#F8FAFC]">{x.t}</h3>
            </div>
            <p className="mt-2 text-xs leading-relaxed text-[#94A3B8]">{x.d}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

