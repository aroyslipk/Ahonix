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
  critical: { label: "Critical", cls: "bg-rose-500/15 text-rose-300 border-rose-800" },
  low: { label: "Low", cls: "bg-amber-500/15 text-amber-300 border-amber-800" },
  healthy: { label: "Healthy", cls: "bg-emerald-500/15 text-emerald-300 border-emerald-800" },
};

export default function Inventory() {
  const { data, isLoading, isError, refetch } = useSection("inventory", "/inventory");
  if (isLoading) return <PageSkeleton />;
  if (isError) return <ErrorState onRetry={refetch} />;
  if (data?.empty) return <EmptyWorkspace name={data.workspace?.name} />;

  const cur = data.workspace.currency;
  const inv = data.inventory;

  return (
    <div className="space-y-8">
      <SectionHeader title="Inventory Forecast" subtitle="Stock health, stock-out forecasts and reorder recommendations" icon={Boxes} />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Card className="p-5"><Stat label="Inventory Value" value={fmtCurrency(inv.total_value, cur)} /></Card>
        <Card className="p-5"><Stat label="Total Units" value={fmtNumber(inv.total_units)} /></Card>
        <Card className="border-rose-900/40 bg-rose-950/10 p-5"><Stat label="Critical (stock-out risk)" value={inv.critical_count} /></Card>
        <Card className="border-amber-900/40 bg-amber-950/10 p-5"><Stat label="Low stock" value={inv.low_count} /></Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="p-5">
          <SectionHeader title="Fast-moving" subtitle="Highest daily demand" />
          <div className="mt-3 space-y-2">
            {inv.fast_moving.map((n) => (
              <div key={n} className="flex items-center gap-2 rounded-lg bg-[#0F111A] px-3 py-2 text-sm text-[#CBD5E1]">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> {n}
              </div>
            ))}
          </div>
        </Card>
        <Card className="p-5">
          <SectionHeader title="Slow-moving" subtitle="Lowest daily demand" />
          <div className="mt-3 space-y-2">
            {inv.slow_moving.map((n) => (
              <div key={n} className="flex items-center gap-2 rounded-lg bg-[#0F111A] px-3 py-2 text-sm text-[#CBD5E1]">
                <span className="h-1.5 w-1.5 rounded-full bg-amber-400" /> {n}
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card className="overflow-hidden">
        <div className="flex items-center justify-between border-b border-[#1E2235] p-5">
          <SectionHeader title="Stock-out forecast" subtitle="Projected from average daily demand" />
          <ValueBadge kind="FORECAST" />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="inventory-table">
            <thead>
              <tr className="border-b border-[#1E2235] text-left text-xs uppercase tracking-wide text-[#64748B]">
                <th className="px-5 py-3 font-medium">Product</th>
                <th className="px-5 py-3 text-right font-medium">Stock</th>
                <th className="px-5 py-3 text-right font-medium">Daily demand</th>
                <th className="px-5 py-3 text-right font-medium">Days left</th>
                <th className="px-5 py-3 text-right font-medium">Stock-out</th>
                <th className="px-5 py-3 text-right font-medium">Reorder</th>
                <th className="px-5 py-3 text-right font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {inv.items.map((it, i) => {
                const st = STATUS[it.status];
                return (
                  <tr key={i} className="border-b border-[#141726] hover:bg-[#161926]">
                    <td className="px-5 py-3 font-medium text-[#F8FAFC]">{it.name}</td>
                    <td className="px-5 py-3 text-right font-metric text-[#CBD5E1]">{fmtNumber(it.stock)}</td>
                    <td className="px-5 py-3 text-right font-metric text-[#CBD5E1]">{it.daily_demand}</td>
                    <td className="px-5 py-3 text-right font-metric font-semibold text-[#F8FAFC]">{it.days_left}d</td>
                    <td className="px-5 py-3 text-right text-[#94A3B8]">{it.stockout_date}</td>
                    <td className="px-5 py-3 text-right font-metric text-emerald-400">+{fmtNumber(it.reorder_qty)}</td>
                    <td className="px-5 py-3 text-right">
                      <Badge className={`border ${st.cls}`}>{st.label}</Badge>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
