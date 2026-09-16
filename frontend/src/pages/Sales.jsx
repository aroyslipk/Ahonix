import React, { useState } from "react";
import { TrendingUp } from "lucide-react";
import { useSection } from "@/lib/hooks";
import { PageSkeleton, ErrorState } from "@/components/StateViews";
import { EmptyWorkspace } from "@/pages/Overview";
import { Card, SectionHeader, Stat } from "@/components/primitives";
import { ValueBadge } from "@/components/ValueBadge";
import { TrendArea, BarSeries, Donut, DONUT_COLORS } from "@/components/charts";
import { fmtCurrency, fmtNumber } from "@/lib/api";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";

export default function Sales() {
  const [metric, setMetric] = useState("revenue");
  const { data, isLoading, isError, refetch } = useSection("sales", "/sales");
  if (isLoading) return <PageSkeleton />;
  if (isError) return <ErrorState onRetry={refetch} />;
  if (data?.empty) return <EmptyWorkspace name={data.workspace?.name} />;

  const cur = data.workspace.currency;
  const s = data.sales;

  return (
    <div className="space-y-8" data-testid="sales-page">
      <SectionHeader
        title="Sales Velocity"
        subtitle="Channel attribution, order volume, and unit economics across all markets"
        icon={TrendingUp}
        right={
          <Select value={metric} onValueChange={setMetric}>
            <SelectTrigger className="w-40 border-[#16221B] bg-[#0B110E] text-xs font-medium text-[#F8FAFC]" data-testid="sales-metric-filter">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="border-[#16221B] bg-[#070C0A] text-xs text-[#F8FAFC]">
              <SelectItem value="revenue">Gross Revenue</SelectItem>
              <SelectItem value="orders">Orders Count</SelectItem>
              <SelectItem value="aov">Avg Order Value</SelectItem>
            </SelectContent>
          </Select>
        }
      />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
        <Card className="p-5">
          <div className="mb-2 flex justify-between">
            <span className="text-xs uppercase tracking-wider text-[#64748B]">Total Revenue</span>
            <ValueBadge kind="ACTUAL" />
          </div>
          <p className="font-metric text-2xl font-bold text-[#F8FAFC]">{fmtCurrency(s.revenue, cur)}</p>
        </Card>
        <Card className="p-5">
          <div className="mb-2 flex justify-between">
            <span className="text-xs uppercase tracking-wider text-[#64748B]">Total Orders</span>
            <ValueBadge kind="ACTUAL" />
          </div>
          <p className="font-metric text-2xl font-bold text-[#F8FAFC]">{fmtNumber(s.orders)}</p>
        </Card>
        <Card className="p-5">
          <div className="mb-2 flex justify-between">
            <span className="text-xs uppercase tracking-wider text-[#64748B]">Avg Order Value</span>
            <ValueBadge kind="ACTUAL" />
          </div>
          <p className="font-metric text-2xl font-bold text-[#F8FAFC]">{fmtCurrency(s.aov, cur)}</p>
        </Card>
      </div>

      <Card className="p-5 sm:p-6">
        <SectionHeader
          title={`${metric === "aov" ? "Average Order Value" : metric === "orders" ? "Order Volume" : "Revenue Trajectory"} Trend`}
          subtitle="12-week velocity baseline · KPI totals cover last 4 weeks"
        />
        <div className="mt-5">
          <BarSeries data={s.weekly} dataKey={metric} xKey="week" currency={cur} prefix={metric === "orders" ? "number" : "currency"} />
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="p-5 sm:p-6">
          <SectionHeader title="Channel Breakdown" subtitle="Revenue attribution across active sales touchpoints" />
          <div className="mt-5 space-y-4">
            {s.by_channel.map((c, i) => {
              const max = Math.max(...s.by_channel.map((x) => x.revenue));
              return (
                <div key={c.channel}>
                  <div className="mb-1.5 flex justify-between text-xs">
                    <span className="font-medium text-[#CBD5E1]">{c.channel}</span>
                    <span className="font-metric font-bold text-[#F8FAFC]">{fmtCurrency(c.revenue, cur)}</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-[#070C0A] border border-[#16221B]">
                    <div className="h-full rounded-full" style={{ width: `${(c.revenue / max) * 100}%`, background: DONUT_COLORS[i % DONUT_COLORS.length] }} />
                  </div>
                  <p className="mt-1 text-[11px] text-[#64748B] font-metric">{fmtNumber(c.orders)} verified orders</p>
                </div>
              );
            })}
          </div>
        </Card>

        <Card className="p-5 sm:p-6">
          <SectionHeader title="Geographic Distribution" subtitle="Top merchant delivery destinations" />
          <div className="mt-5 flex flex-col sm:flex-row sm:items-center gap-6">
            <div className="w-full sm:w-1/2 flex justify-center">
              <Donut data={s.by_country.map((c) => ({ name: c.country, share: c.revenue }))} dataKey="share" />
            </div>
            <div className="flex-1 space-y-2.5">
              {s.by_country.map((c, i) => (
                <div key={c.code} className="flex items-center justify-between text-xs">
                  <span className="flex items-center gap-2 text-[#CBD5E1]">
                    <span className="h-2 w-2 rounded-full" style={{ background: DONUT_COLORS[i % DONUT_COLORS.length] }} />
                    <span>{c.flag}</span>
                    <span>{c.country}</span>
                  </span>
                  <span className="font-metric font-semibold text-[#94A3B8]">{fmtCurrency(c.revenue, cur, true)}</span>
                </div>
              ))}
            </div>
          </div>
        </Card>
      </div>

      <div className="rounded-xl border border-[#16221B] bg-[#0B110E] overflow-hidden">
        <div className="border-b border-[#16221B] bg-[#070C0A] p-5">
          <SectionHeader title="Top Performing Catalog Items" subtitle="Ranked by gross revenue generation" />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-[#16221B] text-left uppercase tracking-wider text-[#64748B]">
                <th className="px-5 py-3 font-semibold">Product</th>
                <th className="px-5 py-3 text-right font-semibold">Units Sold</th>
                <th className="px-5 py-3 text-right font-semibold">Gross Revenue</th>
                <th className="px-5 py-3 text-right font-semibold">Gross Margin</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#121A15]">
              {s.top_products.map((p, i) => (
                <tr key={i} className="hover:bg-[#0E1713] transition-colors">
                  <td className="px-5 py-3.5 font-medium text-[#F8FAFC]">{p.name}</td>
                  <td className="px-5 py-3.5 text-right font-metric text-[#CBD5E1]">{fmtNumber(p.units)}</td>
                  <td className="px-5 py-3.5 text-right font-metric font-semibold text-[#CBD5E1]">{fmtCurrency(p.revenue, cur)}</td>
                  <td className="px-5 py-3.5 text-right font-metric font-bold text-emerald-400">{p.margin}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

