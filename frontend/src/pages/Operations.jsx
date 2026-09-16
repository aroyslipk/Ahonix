import React from "react";
import { Truck, CreditCard, RotateCcw } from "lucide-react";
import { useSection } from "@/lib/hooks";
import { PageSkeleton, ErrorState } from "@/components/StateViews";
import { EmptyWorkspace } from "@/pages/Overview";
import { Card, SectionHeader, Stat } from "@/components/primitives";
import { Donut, DONUT_COLORS } from "@/components/charts";
import { fmtCurrency, fmtNumber } from "@/lib/api";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function Operations() {
  const ops = useSection("operations", "/operations");
  const ret = useSection("returns", "/returns");
  if (ops.isLoading || ret.isLoading) return <PageSkeleton />;
  if (ops.isError) return <ErrorState onRetry={ops.refetch} />;
  if (ops.data?.empty) return <EmptyWorkspace name={ops.data.workspace?.name} />;

  const cur = ops.data?.workspace?.currency || "USD";
  const o = ops.data?.operations;
  const r = ret.data?.returns;
  const isDemo = Boolean(ops.data?.workspace?.is_demo);

  if (!isDemo && (!o || !o.carriers || o.carriers.length === 0)) {
    return (
      <div className="space-y-8" data-testid="operations-empty-state">
        <SectionHeader
          title="Fulfillment & Operating Telemetry"
          subtitle="Carrier margin drag, payment gateway capture rates, and reverse logistics friction"
          icon={Truck}
        />
        <EmptyWorkspace
          name={ops.data?.workspace?.name}
          title="No operations telemetry yet"
          description="Connect your Shopify store or logistics partner in Settings to analyze carrier SLA performance, gateway fees, and returns drag."
        />
      </div>
    );
  }

  const carriers = o?.carriers || [];
  const payments = o?.payments || {};
  const paymentMethods = payments.methods || [];
  const byProduct = r?.by_product || [];
  const byReason = r?.by_reason || [];

  return (
    <div className="space-y-8" data-testid="operations-page">
      <SectionHeader
        title="Fulfillment & Operating Telemetry"
        subtitle="Carrier margin drag, payment gateway capture rates, and reverse logistics friction"
        icon={Truck}
      />

      <Tabs defaultValue="shipping">
        <TabsList className="bg-[#0B110E] border border-[#16221B] p-1 rounded-xl flex overflow-x-auto max-w-full justify-start sm:justify-center">
          <TabsTrigger
            value="shipping"
            data-testid="ops-tab-shipping"
            className="shrink-0 rounded-lg text-xs font-medium data-[state=active]:bg-[#070C0A] data-[state=active]:text-emerald-400 data-[state=active]:border data-[state=active]:border-[#16221B] text-[#94A3B8]"
          >
            <Truck size={13} className="mr-1.5" /> Fulfillment & Logistics
          </TabsTrigger>
          <TabsTrigger
            value="payments"
            data-testid="ops-tab-payments"
            className="shrink-0 rounded-lg text-xs font-medium data-[state=active]:bg-[#070C0A] data-[state=active]:text-emerald-400 data-[state=active]:border data-[state=active]:border-[#16221B] text-[#94A3B8]"
          >
            <CreditCard size={13} className="mr-1.5" /> Gateway Economics
          </TabsTrigger>
          <TabsTrigger
            value="returns"
            data-testid="ops-tab-returns"
            className="shrink-0 rounded-lg text-xs font-medium data-[state=active]:bg-[#070C0A] data-[state=active]:text-emerald-400 data-[state=active]:border data-[state=active]:border-[#16221B] text-[#94A3B8]"
          >
            <RotateCcw size={13} className="mr-1.5" /> Returns & Reverse Logistics
          </TabsTrigger>
        </TabsList>

        {/* SHIPPING */}
        <TabsContent value="shipping" className="mt-6 space-y-6">
          <div className="grid grid-cols-1 gap-3 sm:gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Card className="p-4 sm:p-5"><Stat label="Total Dispatched" value={fmtNumber(o?.shipments || 0)} /></Card>
            <Card className="p-4 sm:p-5"><Stat label="Average Transit" value={`${o?.avg_delivery_days || 0} days`} /></Card>
            <Card className="p-4 sm:p-5"><Stat label="Delivery Failure Rate" value={`${o?.failed_delivery_rate || 0}%`} /></Card>
            <Card className="p-4 sm:p-5"><Stat label="Freight Cost / Unit" value={fmtCurrency(o?.avg_shipping_cost || 0, cur)} /></Card>
          </div>

          <div className="rounded-xl border border-[#16221B] bg-[#0B110E] overflow-hidden">
            <div className="border-b border-[#16221B] bg-[#070C0A] p-5">
              <SectionHeader title="Logistics Carrier Reliability Matrix" subtitle="Unit freight cost, transit velocity, and SLA adherence" />
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-[#16221B] text-left uppercase tracking-wider text-[#64748B]">
                    <th className="px-5 py-3 font-semibold">Carrier</th>
                    <th className="px-5 py-3 text-right font-semibold">Cost / Order</th>
                    <th className="px-5 py-3 text-right font-semibold">Avg Transit</th>
                    <th className="px-5 py-3 text-right font-semibold">Reliability</th>
                    <th className="px-5 py-3 text-right font-semibold">Failure Rate</th>
                    <th className="px-5 py-3 text-right font-semibold">Volume Share</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#121A15]">
                  {carriers.map((cr) => (
                    <tr key={cr.name} className="hover:bg-[#0E1713] transition-colors">
                      <td className="px-5 py-3.5 font-medium text-[#F8FAFC]">{cr.name}</td>
                      <td className="px-5 py-3.5 text-right font-metric text-[#CBD5E1]">{fmtCurrency(cr.cost || 0, cur)}</td>
                      <td className="px-5 py-3.5 text-right font-metric text-[#CBD5E1]">{cr.avg_days || 0}d</td>
                      <td className="px-5 py-3.5 text-right font-metric font-bold text-emerald-400">{cr.reliability || 0}%</td>
                      <td className="px-5 py-3.5 text-right font-metric font-bold text-rose-300">{cr.failure_rate || 0}%</td>
                      <td className="px-5 py-3.5 text-right font-metric text-[#94A3B8]">{cr.volume_share || 0}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </TabsContent>

        {/* PAYMENTS */}
        <TabsContent value="payments" className="mt-6 space-y-6">
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <Card className="p-5"><Stat label="Authorization Rate" value={`${payments.success_rate || 0}%`} /></Card>
            <Card className="p-5"><Stat label="Declined / Failed" value={`${payments.failure_rate || 0}%`} /></Card>
            <Card className="p-5"><Stat label="Effective Processing Rate" value={`${payments.avg_fee_pct || 0}%`} /></Card>
            <Card className="p-5"><Stat label="Accumulated Gateway Fees" value={fmtCurrency(payments.total_fees || 0, cur)} /></Card>
          </div>
          <Card className="p-5 sm:p-6">
            <SectionHeader title="Payment Method Share & Conversion" subtitle="Breakdown of customer checkout preferences and gateway health" />
            <div className="mt-5 space-y-3.5">
              {paymentMethods.length === 0 ? (
                <p className="text-xs text-[#64748B] py-3 text-center">No payment gateway records available.</p>
              ) : (
                paymentMethods.map((mth, i) => (
                  <div key={mth.method || i} className="flex items-center gap-4">
                    <div className="w-44 shrink-0 text-xs font-semibold text-[#CBD5E1]">{mth.method}</div>
                    <div className="flex-1">
                      <div className="h-2 overflow-hidden rounded-full bg-[#070C0A] border border-[#16221B]">
                        <div className="h-full rounded-full" style={{ width: `${mth.share || 0}%`, background: DONUT_COLORS[i % DONUT_COLORS.length] }} />
                      </div>
                    </div>
                    <div className="w-16 text-right font-metric text-xs text-[#94A3B8]">{mth.share || 0}% share</div>
                    <div className="w-28 text-right font-metric text-xs font-bold text-emerald-400">{mth.success || 0}% success</div>
                  </div>
                ))
              )}
            </div>
          </Card>
        </TabsContent>

        {/* RETURNS */}
        <TabsContent value="returns" className="mt-6 space-y-6">
          {r && (
            <>
              <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
                <Card className="p-5"><Stat label="Returned Units" value={fmtNumber(r.total_returns)} /></Card>
                <Card className="p-5"><Stat label="Catalog Return Rate" value={`${r.return_rate}%`} /></Card>
                <Card className="p-5"><Stat label="Reverse Logistics Cost" value={fmtCurrency(r.return_cost, cur)} /></Card>
                <Card className="p-5"><Stat label="Top 3 Products Share" value={`${r.top3_share}%`} sub="of total return expense" /></Card>
              </div>

              <div className="rounded-xl border border-rose-500/30 bg-rose-950/15 p-5">
                <h3 className="font-display text-sm font-bold text-[#F8FAFC]">Concentrated Return Drag Detected</h3>
                <p className="mt-1 text-xs leading-relaxed text-[#CBD5E1]">
                  {r.by_product.slice(0, 3).map((x) => x.name).join(", ")} account for {r.top3_share}% of all return costs.
                  Primary root causes include expectation mismatches and sizing ambiguities. Mitigating friction across these 3 SKUs recovers {fmtCurrency(r.return_cost * 0.4, cur)} in lost margin.
                </p>
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                <Card className="p-5 sm:p-6">
                  <SectionHeader title="Return Friction Drivers" subtitle="Customer-reported reasons" />
                  <div className="mt-5 space-y-3">
                    {r.by_reason.map((rr, i) => (
                      <div key={rr.reason}>
                        <div className="mb-1.5 flex justify-between text-xs">
                          <span className="text-[#CBD5E1]">{rr.reason}</span>
                          <span className="font-metric font-semibold text-[#94A3B8]">{rr.share}%</span>
                        </div>
                        <div className="h-2 overflow-hidden rounded-full bg-[#070C0A] border border-[#16221B]">
                          <div className="h-full rounded-full" style={{ width: `${rr.share}%`, background: DONUT_COLORS[i % DONUT_COLORS.length] }} />
                        </div>
                      </div>
                    ))}
                  </div>
                </Card>

                <div className="rounded-xl border border-[#16221B] bg-[#0B110E] overflow-hidden">
                  <div className="border-b border-[#16221B] bg-[#070C0A] p-5">
                    <SectionHeader title="Highest Return Cost Items" subtitle="Ranked by total reversal expense" />
                  </div>
                  <div className="max-h-72 overflow-y-auto">
                    <table className="w-full text-xs">
                      <tbody className="divide-y divide-[#121A15]">
                        {r.by_product.map((x, i) => (
                          <tr key={i} className="hover:bg-[#0E1713] transition-colors">
                            <td className="px-5 py-3 font-medium text-[#F8FAFC]">{x.name}</td>
                            <td className="px-5 py-3 text-right font-metric text-[#94A3B8]">{x.return_rate}%</td>
                            <td className="px-5 py-3 text-right font-metric font-semibold text-rose-300">{fmtCurrency(x.cost, cur)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

