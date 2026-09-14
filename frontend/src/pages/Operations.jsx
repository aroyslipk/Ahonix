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

  const cur = ops.data.workspace.currency;
  const o = ops.data.operations;
  const r = ret.data?.returns;

  return (
    <div className="space-y-8">
      <SectionHeader title="Operations" subtitle="Shipping, payments and returns intelligence" icon={Truck} />

      <Tabs defaultValue="shipping">
        <TabsList className="bg-[#0F111A] border border-[#1E2235]">
          <TabsTrigger value="shipping" data-testid="ops-tab-shipping" className="data-[state=active]:bg-emerald-500/15 data-[state=active]:text-emerald-300">
            <Truck size={14} className="mr-1.5" /> Shipping
          </TabsTrigger>
          <TabsTrigger value="payments" data-testid="ops-tab-payments" className="data-[state=active]:bg-emerald-500/15 data-[state=active]:text-emerald-300">
            <CreditCard size={14} className="mr-1.5" /> Payments
          </TabsTrigger>
          <TabsTrigger value="returns" data-testid="ops-tab-returns" className="data-[state=active]:bg-emerald-500/15 data-[state=active]:text-emerald-300">
            <RotateCcw size={14} className="mr-1.5" /> Returns
          </TabsTrigger>
        </TabsList>

        {/* SHIPPING */}
        <TabsContent value="shipping" className="mt-6 space-y-6">
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <Card className="p-5"><Stat label="Shipments" value={fmtNumber(o.shipments)} /></Card>
            <Card className="p-5"><Stat label="Avg Delivery" value={`${o.avg_delivery_days}d`} /></Card>
            <Card className="p-5"><Stat label="Failed Delivery" value={`${o.failed_delivery_rate}%`} /></Card>
            <Card className="p-5"><Stat label="Avg Shipping Cost" value={fmtCurrency(o.avg_shipping_cost, cur)} /></Card>
          </div>
          <Card className="overflow-hidden">
            <div className="border-b border-[#1E2235] p-5"><SectionHeader title="Carrier comparison" subtitle="Cost, speed, reliability and failure rate" /></div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[#1E2235] text-left text-xs uppercase tracking-wide text-[#64748B]">
                    <th className="px-5 py-3 font-medium">Carrier</th>
                    <th className="px-5 py-3 text-right font-medium">Cost/order</th>
                    <th className="px-5 py-3 text-right font-medium">Avg days</th>
                    <th className="px-5 py-3 text-right font-medium">Reliability</th>
                    <th className="px-5 py-3 text-right font-medium">Failure</th>
                    <th className="px-5 py-3 text-right font-medium">Volume</th>
                  </tr>
                </thead>
                <tbody>
                  {o.carriers.map((cr) => (
                    <tr key={cr.name} className="border-b border-[#141726] hover:bg-[#161926]">
                      <td className="px-5 py-3 font-medium text-[#F8FAFC]">{cr.name}</td>
                      <td className="px-5 py-3 text-right font-metric text-[#CBD5E1]">{fmtCurrency(cr.cost, cur)}</td>
                      <td className="px-5 py-3 text-right font-metric text-[#CBD5E1]">{cr.avg_days}</td>
                      <td className="px-5 py-3 text-right font-metric text-emerald-400">{cr.reliability}%</td>
                      <td className="px-5 py-3 text-right font-metric text-rose-300">{cr.failure_rate}%</td>
                      <td className="px-5 py-3 text-right font-metric text-[#94A3B8]">{cr.volume_share}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </TabsContent>

        {/* PAYMENTS */}
        <TabsContent value="payments" className="mt-6 space-y-6">
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <Card className="p-5"><Stat label="Success Rate" value={`${o.payments.success_rate}%`} /></Card>
            <Card className="p-5"><Stat label="Failure Rate" value={`${o.payments.failure_rate}%`} /></Card>
            <Card className="p-5"><Stat label="Avg Fee" value={`${o.payments.avg_fee_pct}%`} /></Card>
            <Card className="p-5"><Stat label="Total Fees" value={fmtCurrency(o.payments.total_fees, cur)} /></Card>
          </div>
          <Card className="p-5">
            <SectionHeader title="Payment methods" subtitle="Share and success rate" />
            <div className="mt-4 space-y-3">
              {o.payments.methods.map((mth, i) => (
                <div key={mth.method} className="flex items-center gap-4">
                  <div className="w-40 shrink-0 text-sm text-[#CBD5E1]">{mth.method}</div>
                  <div className="flex-1">
                    <div className="h-2.5 overflow-hidden rounded-full bg-[#0F111A]">
                      <div className="h-full rounded-full" style={{ width: `${mth.share}%`, background: DONUT_COLORS[i % DONUT_COLORS.length] }} />
                    </div>
                  </div>
                  <div className="w-14 text-right font-metric text-xs text-[#94A3B8]">{mth.share}%</div>
                  <div className="w-24 text-right text-xs text-emerald-400">{mth.success}% success</div>
                </div>
              ))}
            </div>
          </Card>
        </TabsContent>

        {/* RETURNS */}
        <TabsContent value="returns" className="mt-6 space-y-6">
          {r && (
            <>
              <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
                <Card className="p-5"><Stat label="Total Returns" value={fmtNumber(r.total_returns)} /></Card>
                <Card className="p-5"><Stat label="Return Rate" value={`${r.return_rate}%`} /></Card>
                <Card className="p-5"><Stat label="Return Cost" value={fmtCurrency(r.return_cost, cur)} /></Card>
                <Card className="p-5"><Stat label="Top 3 products" value={`${r.top3_share}%`} sub="of return cost" /></Card>
              </div>
              <Card className="border-l-4 border-l-rose-500 bg-rose-950/10 p-5">
                <h3 className="font-display text-sm font-bold text-[#F8FAFC]">Three products drive most of your returns</h3>
                <p className="mt-1 text-sm text-[#94A3B8]">
                  {r.by_product.slice(0, 3).map((x) => x.name).join(", ")} account for {r.top3_share}% of return cost.
                  Likely drivers: sizing, product expectations and image/description quality. Improving these could recover a
                  meaningful share of the {fmtCurrency(r.return_cost, cur)} return cost.
                </p>
              </Card>
              <div className="grid gap-4 lg:grid-cols-2">
                <Card className="p-5">
                  <SectionHeader title="Returns by reason" />
                  <div className="mt-4 space-y-3">
                    {r.by_reason.map((rr, i) => (
                      <div key={rr.reason}>
                        <div className="mb-1 flex justify-between text-sm"><span className="text-[#CBD5E1]">{rr.reason}</span><span className="font-metric text-[#94A3B8]">{rr.share}%</span></div>
                        <div className="h-2 overflow-hidden rounded-full bg-[#0F111A]"><div className="h-full rounded-full" style={{ width: `${rr.share}%`, background: DONUT_COLORS[i % DONUT_COLORS.length] }} /></div>
                      </div>
                    ))}
                  </div>
                </Card>
                <Card className="overflow-hidden">
                  <div className="border-b border-[#1E2235] p-5"><SectionHeader title="Returns by product" /></div>
                  <div className="max-h-72 overflow-y-auto">
                    <table className="w-full text-sm">
                      <tbody>
                        {r.by_product.map((x, i) => (
                          <tr key={i} className="border-b border-[#141726]">
                            <td className="px-5 py-2.5 text-[#F8FAFC]">{x.name}</td>
                            <td className="px-5 py-2.5 text-right font-metric text-[#94A3B8]">{x.return_rate}%</td>
                            <td className="px-5 py-2.5 text-right font-metric text-rose-300">{fmtCurrency(x.cost, cur)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Card>
              </div>
            </>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
