import React, { useState } from "react";
import { Globe, Rocket, Loader2, Compass, ShieldAlert } from "lucide-react";
import { useSection } from "@/lib/hooks";
import { api, fmtCurrency, fmtNumber } from "@/lib/api";
import { PageSkeleton, ErrorState } from "@/components/StateViews";
import { EmptyWorkspace } from "@/pages/Overview";
import { Card, SectionHeader, Stat } from "@/components/primitives";
import { ValueBadge } from "@/components/ValueBadge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

function Meter({ label, value, max = 100, suffix = "", color = "#00E599" }) {
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs"><span className="text-[#94A3B8]">{label}</span><span className="font-metric font-semibold text-[#CBD5E1]">{value}{suffix}</span></div>
      <div className="h-1.5 overflow-hidden rounded-full bg-[#070C0A] border border-[#16221B]">
        <div className="h-full rounded-full" style={{ width: `${(value / max) * 100}%`, background: color }} />
      </div>
    </div>
  );
}

export default function Markets() {
  const { data, isLoading, isError, refetch } = useSection("markets", "/markets");
  const [sim, setSim] = useState({ country: "Germany", price: 89, demand_units: 400, inventory_units: 300, marketing_budget: 5000 });
  const [result, setResult] = useState(null);
  const [running, setRunning] = useState(false);

  if (isLoading) return <PageSkeleton />;
  if (isError) return <ErrorState onRetry={refetch} />;
  if (data?.empty) return <EmptyWorkspace name={data.workspace?.name} />;

  const cur = data?.workspace?.currency || "USD";
  const markets = data?.markets || [];
  const isDemo = Boolean(data?.workspace?.is_demo);

  const runSim = async () => {
    setRunning(true);
    try {
      const { data: res } = await api.post("/markets/simulate", {
        ...sim,
        price: Number(sim.price),
        demand_units: Number(sim.demand_units),
        inventory_units: Number(sim.inventory_units),
        marketing_budget: Number(sim.marketing_budget),
      });
      setResult(res.result);
    } catch {
      setResult(null);
    } finally {
      setRunning(false);
    }
  };

  if (!isDemo && markets.length === 0) {
    return (
      <div className="space-y-8" data-testid="markets-empty-state">
        <SectionHeader
          title="Market Intelligence & Expansion"
          subtitle="Cross-border demand analysis, margin feasibility, and entry simulation"
          icon={Globe}
        />
        <EmptyWorkspace
          name={data?.workspace?.name}
          title="No market expansion data yet"
          description="Connect international sales channels or Shopify Markets in Settings to evaluate regional demand, operating margins, and cross-border feasibility."
        />
      </div>
    );
  }

  return (
    <div className="space-y-8" data-testid="markets-page">
      <SectionHeader
        title="Market Intelligence & Expansion"
        subtitle="Cross-border demand analysis, margin feasibility, and entry simulation"
        icon={Globe}
        right={<ValueBadge kind="DEMO" />}
      />

      <Tabs defaultValue="opportunities">
        <TabsList className="border border-[#16221B] bg-[#0B110E] p-1 rounded-xl">
          <TabsTrigger
            value="opportunities"
            data-testid="markets-tab-opps"
            className="rounded-lg text-xs font-medium data-[state=active]:bg-[#070C0A] data-[state=active]:text-emerald-400 data-[state=active]:border data-[state=active]:border-[#16221B] text-[#94A3B8]"
          >
            Regional Opportunities
          </TabsTrigger>
          <TabsTrigger
            value="simulator"
            data-testid="markets-tab-sim"
            className="rounded-lg text-xs font-medium data-[state=active]:bg-[#070C0A] data-[state=active]:text-emerald-400 data-[state=active]:border data-[state=active]:border-[#16221B] text-[#94A3B8]"
          >
            Launch Feasibility Simulator
          </TabsTrigger>
        </TabsList>

        <TabsContent value="opportunities" className="mt-6">
          <div className="grid gap-4 lg:grid-cols-2">
            {markets.map((m) => (
              <Card key={m.code} className="p-5 sm:p-6" data-testid={`market-card-${m.code}`}>
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-display text-lg font-bold text-[#F8FAFC]">{m.flag} {m.country}</h3>
                    <p className="text-xs text-[#64748B]">Current baseline revenue {fmtCurrency(m.current_revenue, cur, true)}</p>
                  </div>
                  <div className="text-right">
                    <p className="font-metric text-2xl font-bold text-emerald-400">{m.opportunity_score}</p>
                    <p className="text-[10px] uppercase tracking-wider text-[#64748B]">Opportunity Index</p>
                  </div>
                </div>
                <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-x-5 gap-y-3">
                  <Meter label="Organic Demand" value={m.demand} />
                  <Meter label="Competitive Saturation" value={m.competition} color="#F59E0B" />
                  <Meter label="Projected Operating Margin" value={m.projected_margin} max={40} suffix="%" />
                  <div className="flex flex-col justify-center gap-1 text-xs">
                    <span className="text-[#94A3B8]">Freight Complexity: <span className="font-semibold text-[#CBD5E1]">{m.shipping_complexity}</span></span>
                    <span className="text-[#94A3B8]">Return Vulnerability: <span className="font-semibold text-[#CBD5E1]">{m.return_risk}</span></span>
                  </div>
                </div>
                <div className="mt-4 flex items-start gap-2.5 rounded-lg border border-[#16221B] bg-[#070C0A] p-3 text-xs leading-relaxed text-[#CBD5E1]">
                  <Compass size={14} className="mt-0.5 shrink-0 text-emerald-400" />
                  <p>
                    {m.opportunity_score >= 80
                      ? `High conviction entry — ${m.existing_traffic.toLowerCase()} organic baseline with defensible unit margins. Prioritize currency-native checkout.`
                      : m.opportunity_score >= 65
                      ? `Moderate opportunity — robust demand but requires mitigation against ${m.return_risk.toLowerCase()} return drag and ${m.shipping_complexity.toLowerCase()} freight complexity.`
                      : `Constrained upside — elevated competitive bid pressure. Test demand with staged warehouse allocation prior to full rollout.`}
                  </p>
                </div>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="simulator" className="mt-6">
          <div className="grid gap-6 lg:grid-cols-2">
            <Card className="p-6">
              <SectionHeader title="Simulate Regional Expansion" subtitle="Model capital requirements and margin impact" icon={Rocket} />
              <div className="mt-5 space-y-4">
                <div>
                  <Label className="text-xs font-medium text-[#94A3B8]">Target Country</Label>
                  <Select value={sim.country} onValueChange={(v) => setSim({ ...sim, country: v })}>
                    <SelectTrigger className="mt-1.5 border-[#16221B] bg-[#070C0A] text-xs text-[#F8FAFC]" data-testid="sim-country"><SelectValue /></SelectTrigger>
                    <SelectContent className="border-[#16221B] bg-[#070C0A] text-xs text-[#F8FAFC]">
                      {data.markets.map((m) => <SelectItem key={m.code} value={m.country}>{m.flag} {m.country}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                {[
                  ["Expected Retail Price", "price"], ["Projected 30-Day Demand (units)", "demand_units"],
                  ["Staged Inventory (units)", "inventory_units"], ["Launch Ad Budget", "marketing_budget"],
                ].map(([label, key]) => (
                  <div key={key}>
                    <Label className="text-xs font-medium text-[#94A3B8]">{label}</Label>
                    <Input type="number" value={sim[key]} onChange={(e) => setSim({ ...sim, [key]: e.target.value })}
                      className="mt-1.5 border-[#16221B] bg-[#070C0A] text-xs text-[#F8FAFC]" data-testid={`sim-${key}`} />
                  </div>
                ))}
                <Button onClick={runSim} disabled={running} className="w-full bg-emerald-500 font-semibold text-emerald-950 hover:bg-emerald-400 text-xs" data-testid="sim-run-btn">
                  {running ? <Loader2 className="animate-spin" size={16} /> : <>Calculate Expansion Economics <Rocket size={14} className="ml-1.5" /></>}
                </Button>
              </div>
            </Card>

            <Card className="p-6">
              <div className="flex items-center justify-between">
                <SectionHeader title="Pro Forma Projection" subtitle="Simulated unit margins and payback timeline" />
                <ValueBadge kind="PROJECTED" />
              </div>
              {!result ? (
                <div className="mt-14 flex flex-col items-center text-center text-xs text-[#64748B]">
                  <Rocket size={26} className="mb-3 text-[#334155]" />
                  Execute simulation to evaluate expected return, breakeven velocity, and risk parameters.
                </div>
              ) : (
                <div className="mt-5 space-y-4" data-testid="sim-result">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <Stat label="Projected Gross Revenue" value={fmtCurrency(result.projected_revenue, cur)} />
                    <Stat label="Projected True Profit" value={fmtCurrency(result.projected_profit, cur)} />
                    <Stat label="Est. Orders (4 wk)" value={fmtNumber(result.estimated_orders)} />
                    <Stat label="Est. Blended CAC" value={fmtCurrency(result.estimated_cac, cur)} />
                    <Stat label="Committed Inventory" value={fmtNumber(result.required_inventory)} />
                    <Stat label="Expected Return Friction" value={`${result.estimated_return_risk}%`} sub={result.return_risk_label} />
                    <Stat label="Capital Payback" value={result.breakeven_weeks ? `${result.breakeven_weeks} weeks` : "—"} />
                    <Stat label="Feasibility Score" value={result.opportunity_score} />
                  </div>
                  <div className="rounded-lg border border-[#16221B] bg-[#070C0A] p-3 text-xs leading-relaxed">
                    <p className="text-[#94A3B8]"><span className="font-semibold text-rose-300">Primary Friction Vector: </span>{result.main_risk}</p>
                  </div>
                  <div className="flex items-start gap-2.5 rounded-lg border border-emerald-500/20 bg-[#0B1A13] p-3 text-xs leading-relaxed">
                    <Compass size={15} className="mt-0.5 shrink-0 text-emerald-400" />
                    <p className="text-[#CBD5E1]"><span className="font-semibold text-emerald-300">Deployment Strategy: </span>{result.strategy}</p>
                  </div>
                </div>
              )}
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

