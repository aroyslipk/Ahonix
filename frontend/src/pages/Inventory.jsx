import React from "react";
import { Boxes, AlertTriangle } from "lucide-react";
import { useSection } from "@/lib/hooks";
import { PageSkeleton, ErrorState } from "@/components/StateViews";
import { EmptyWorkspace } from "@/pages/Overview";
import { Card, SectionHeader, Stat } from "@/components/primitives";
import { ValueBadge } from "@/components/ValueBadge";
import { fmtCurrency, fmtNumber } from "@/lib/api";
import { Badge } from "@/components/ui/badge";

const STATUS = {
  critical: { label: "Critical Stock", cls: "bg-rose-500/10 text-rose-300 border-rose-500/30" },
  low: { label: "Low Cover", cls: "bg-amber-500/10 text-amber-300 border-amber-500/30" },
  healthy: { label: "Optimal", cls: "bg-emerald-500/10 text-emerald-300 border-emerald-500/30" },
};

export default function Inventory() {
  const { data, isLoading, isError, refetch } = useSection("inventory", "/inventory");
  if (isLoading) return <PageSkeleton />;
  if (isError) return <ErrorState onRetry={refetch} />;
  if (data?.empty) return <EmptyWorkspace name={data.workspace?.name} />;

  const cur = data.workspace.currency;
  const inv = data.inventory;

  return (
    <div className="space-y-8" data-testid="inventory-page">
      <SectionHeader
        title="Inventory Diagnostics & Cover"
        subtitle="Stock runout modeling, velocity forecasting, and replenishment optimization"
        icon={Boxes}
      />

      <div className="grid grid-cols-1 gap-3 sm:gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="p-4 sm:p-5"><Stat label="Active Stock Value" value={fmtCurrency(inv.total_value, cur)} /></Card>
        <Card className="p-4 sm:p-5"><Stat label="Total Warehouse Units" value={fmtNumber(inv.total_units)} /></Card>
        <Card className="border-rose-500/30 bg-rose-950/15 p-4 sm:p-5"><Stat label="Immediate Stock-out Risk" value={inv.critical_count} sub="Requires immediate PO" /></Card>
        <Card className="border-amber-500/30 bg-amber-950/15 p-4 sm:p-5"><Stat label="Low Velocity Cover" value={inv.low_count} sub="&lt; 14 days runout" /></Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="p-5 sm:p-6">
          <SectionHeader title="High Turnover Catalog" subtitle="Highest units depleted per operating day" />
          <div className="mt-4 space-y-2">
            {inv.fast_moving.map((n) => (
              <div key={n} className="flex items-center gap-2.5 rounded-lg border border-[#16221B] bg-[#070C0A] px-3.5 py-2.5 text-xs text-[#CBD5E1]">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                <span className="font-medium text-[#F8FAFC]">{n}</span>
              </div>
            ))}
          </div>
        </Card>
        <Card className="p-5 sm:p-6">
          <SectionHeader title="Capital Traps / Slow Turn" subtitle="Lowest units depleted per operating day" />
          <div className="mt-4 space-y-2">
            {inv.slow_moving.map((n) => (
              <div key={n} className="flex items-center gap-2.5 rounded-lg border border-[#16221B] bg-[#070C0A] px-3.5 py-2.5 text-xs text-[#CBD5E1]">
                <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
                <span className="font-medium text-[#CBD5E1]">{n}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <div className="rounded-xl border border-[#16221B] bg-[#0B110E] overflow-hidden">
        <div className="flex items-center justify-between border-b border-[#16221B] bg-[#070C0A] p-5">
          <SectionHeader title="Stock-Out Forecast Matrix" subtitle="Calculated from real 28-day daily demand velocity" />
          <ValueBadge kind="FORECAST" />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs" data-testid="inventory-table">
            <thead>
              <tr className="border-b border-[#16221B] text-left uppercase tracking-wider text-[#64748B]">
                <th className="px-5 py-3 font-semibold">Product</th>
                <th className="px-5 py-3 text-right font-semibold">Available Units</th>
                <th className="px-5 py-3 text-right font-semibold">Daily Run-rate</th>
                <th className="px-5 py-3 text-right font-semibold">Runout Days</th>
                <th className="px-5 py-3 text-right font-semibold">Projected Zero</th>
                <th className="px-5 py-3 text-right font-semibold">Recommended PO</th>
                <th className="px-5 py-3 text-right font-semibold">Stock Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#121A15]">
              {inv.items.map((it, i) => {
                const st = STATUS[it.status] || STATUS.healthy;
                return (
                  <tr key={i} className="hover:bg-[#0E1713] transition-colors">
                    <td className="px-5 py-3.5 font-medium text-[#F8FAFC]">{it.name}</td>
                    <td className="px-5 py-3.5 text-right font-metric text-[#CBD5E1]">{fmtNumber(it.stock)}</td>
                    <td className="px-5 py-3.5 text-right font-metric text-[#CBD5E1]">{it.daily_demand}/day</td>
                    <td className="px-5 py-3.5 text-right font-metric font-bold text-[#F8FAFC]">{it.days_left}d</td>
                    <td className="px-5 py-3.5 text-right text-[#94A3B8] font-metric">{it.stockout_date}</td>
                    <td className="px-5 py-3.5 text-right font-metric font-bold text-emerald-400">+{fmtNumber(it.reorder_qty)}</td>
                    <td className="px-5 py-3.5 text-right">
                      <Badge className={`border text-[10px] font-semibold uppercase tracking-wider ${st.cls}`}>{st.label}</Badge>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

