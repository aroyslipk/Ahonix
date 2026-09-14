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
    <div className="space-y-8">
      <SectionHeader
        title="Sales"
        subtitle="Revenue, orders and channel performance"
        icon={TrendingUp}
        right={
          <Select value={metric} onValueChange={setMetric}>
            <SelectTrigger className="w-40 border-[#2D334B] bg-[#0F111A] text-sm text-[#F8FAFC]" data-testid="sales-metric-filter">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="border-[#2D334B] bg-[#0F111A] text-[#F8FAFC]">
              <SelectItem value="revenue">Revenue</SelectItem>
              <SelectItem value="orders">Orders</SelectItem>
              <SelectItem value="aov">Avg Order Value</SelectItem>
            </SelectContent>
          </Select>
        }
      />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
        <Card className="p-5"><div className="mb-2 flex justify-between"><span className="text-xs text-[#94A3B8]">Total Revenue</span><ValueBadge kind="ACTUAL" /></div><p className="font-metric text-2xl font-extrabold text-[#F8FAFC]">{fmtCurrency(s.revenue, cur)}</p></Card>
        <Card className="p-5"><div className="mb-2 flex justify-between"><span className="text-xs text-[#94A3B8]">Orders</span><ValueBadge kind="ACTUAL" /></div><p className="font-metric text-2xl font-extrabold text-[#F8FAFC]">{fmtNumber(s.orders)}</p></Card>
        <Card className="p-5"><div className="mb-2 flex justify-between"><span className="text-xs text-[#94A3B8]">Avg Order Value</span><ValueBadge kind="ACTUAL" /></div><p className="font-metric text-2xl font-extrabold text-[#F8FAFC]">{fmtCurrency(s.aov, cur)}</p></Card>
      </div>

      <Card className="p-5">
        <SectionHeader title={`${metric === "aov" ? "Average order value" : metric === "orders" ? "Order volume" : "Revenue"} trend`} subtitle="12-week history for context · KPI totals above cover last 4 weeks" />
        <div className="mt-4">
          <BarSeries data={s.weekly} dataKey={metric} xKey="week" currency={cur} prefix={metric === "orders" ? "number" : "currency"} />
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="p-5">
          <SectionHeader title="Sales by channel" />
          <div className="mt-4 space-y-3">
            {s.by_channel.map((c, i) => {
              const max = Math.max(...s.by_channel.map((x) => x.revenue));
              return (
                <div key={c.channel}>
                  <div className="mb-1 flex justify-between text-sm">
                    <span className="text-[#CBD5E1]">{c.channel}</span>
                    <span className="font-metric font-semibold text-[#F8FAFC]">{fmtCurrency(c.revenue, cur)}</span>
                  </div>
                  <div className="h-2.5 overflow-hidden rounded-full bg-[#0F111A]">
                    <div className="h-full rounded-full" style={{ width: `${(c.revenue / max) * 100}%`, background: DONUT_COLORS[i] }} />
                  </div>
                  <p className="mt-0.5 text-xs text-[#64748B]">{fmtNumber(c.orders)} orders</p>
                </div>
              );
            })}
          </div>
        </Card>

        <Card className="p-5">
          <SectionHeader title="Revenue by country" />
          <div className="mt-4 flex items-center gap-4">
            <div className="w-1/2">
              <Donut data={s.by_country.map((c) => ({ name: c.country, share: c.revenue }))} dataKey="share" />
            </div>
            <div className="flex-1 space-y-2">
              {s.by_country.map((c, i) => (
                <div key={c.code} className="flex items-center justify-between text-sm">
                  <span className="flex items-center gap-2 text-[#CBD5E1]">
                    <span className="h-2.5 w-2.5 rounded-full" style={{ background: DONUT_COLORS[i % DONUT_COLORS.length] }} />
                    {c.flag} {c.country}
                  </span>
                  <span className="font-metric text-[#94A3B8]">{fmtCurrency(c.revenue, cur, true)}</span>
                </div>
              ))}
            </div>
          </div>
        </Card>
      </div>

      <Card className="overflow-hidden">
        <div className="border-b border-[#1E2235] p-5"><SectionHeader title="Top products" subtitle="By revenue" /></div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#1E2235] text-left text-xs uppercase tracking-wide text-[#64748B]">
                <th className="px-5 py-3 font-medium">Product</th>
                <th className="px-5 py-3 text-right font-medium">Units</th>
                <th className="px-5 py-3 text-right font-medium">Revenue</th>
                <th className="px-5 py-3 text-right font-medium">Margin</th>
              </tr>
            </thead>
            <tbody>
              {s.top_products.map((p, i) => (
                <tr key={i} className="border-b border-[#141726] hover:bg-[#161926]">
                  <td className="px-5 py-3 font-medium text-[#F8FAFC]">{p.name}</td>
                  <td className="px-5 py-3 text-right font-metric text-[#CBD5E1]">{fmtNumber(p.units)}</td>
                  <td className="px-5 py-3 text-right font-metric text-[#CBD5E1]">{fmtCurrency(p.revenue, cur)}</td>
                  <td className="px-5 py-3 text-right font-metric text-emerald-400">{p.margin}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
