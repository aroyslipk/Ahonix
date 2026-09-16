import React from "react";
import { useNavigate } from "react-router-dom";
import {
  Wallet,
  Sparkles,
  ArrowDownRight,
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  HelpCircle,
  ShieldCheck,
  TrendingUp,
} from "lucide-react";
import { useSection } from "@/lib/hooks";
import { PageSkeleton, ErrorState } from "@/components/StateViews";
import { EmptyWorkspace } from "@/pages/Overview";
import { Card, SectionHeader, Stat } from "@/components/primitives";
import { ValueBadge } from "@/components/ValueBadge";
import { Button } from "@/components/ui/button";
import { fmtCurrency, fmtPercent, fmtNumber } from "@/lib/api";

export default function TrueProfit() {
  const navigate = useNavigate();
  const { data, isLoading, isError, refetch } = useSection("profit", "/profit");
  if (isLoading) return <PageSkeleton />;
  if (isError) return <ErrorState onRetry={refetch} />;
  if (data?.empty) return <EmptyWorkspace name={data.workspace?.name} />;

  const cur = data.workspace.currency;
  const p = data.profit;
  const gross = p.gross_revenue;
  const profitBadgeKind = p.cogs_kind || (data.workspace?.is_demo ? "ACTUAL" : "ESTIMATED");

  const completeness = p.financial_completeness || { status: "PARTIAL", reasons: [] };
  const completenessStatus = completeness.status || "PARTIAL";
  const completenessReasons = completeness.reasons || [];
  const excludedAdSpend = p.excluded_ad_spend || 0.0;
  const eligibleAdSpend = p.eligible_ad_spend || 0.0;

  return (
    <div className="space-y-8" data-testid="true-profit-page">
      <SectionHeader
        title="True Profit Engine"
        subtitle="What you actually keep after every hidden cost · last 4 weeks"
        icon={Wallet}
        right={
          <div className="flex items-center gap-2">
            <span className="text-xs text-[#64748B]">Completeness:</span>
            <span
              className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide border ${
                completenessStatus === "FULL"
                  ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                  : completenessStatus === "PARTIAL"
                  ? "border-amber-500/30 bg-amber-500/10 text-amber-300"
                  : "border-[#2D334B] bg-[#161926] text-[#94A3B8]"
              }`}
              data-testid="true-profit-completeness-badge"
            >
              {completenessStatus === "FULL" && <CheckCircle2 size={12} className="text-emerald-400" />}
              {completenessStatus === "PARTIAL" && <AlertTriangle size={12} className="text-amber-400" />}
              {completenessStatus}
            </span>
            <ValueBadge kind={profitBadgeKind} />
          </div>
        }
      />

      {/* Financial Completeness Status Banner */}
      {completenessStatus === "FULL" ? (
        <div
          className="flex items-center gap-2.5 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-xs text-emerald-300"
          data-testid="completeness-full-banner"
        >
          <ShieldCheck size={18} className="shrink-0 text-emerald-400" />
          <span>
            <strong>Financial Completeness: FULL.</strong> All inputs (Shopify Gross Revenue, 100% merchant COGS, and real synced advertising expenses) are verified for this 28-day window.
          </span>
        </div>
      ) : (
        <div
          className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-xs text-amber-200"
          data-testid="completeness-partial-banner"
        >
          <div className="flex items-start gap-2.5">
            <AlertTriangle size={17} className="shrink-0 mt-0.5 text-amber-400" />
            <div className="space-y-1">
              <p className="font-semibold text-amber-100">
                Financial Completeness is {completenessStatus}
              </p>
              <ul className="list-disc pl-4 space-y-0.5 text-amber-200/90">
                {completenessReasons.map((reason, idx) => (
                  <li key={idx}>{reason}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Currency Mismatch Exclusion Notice */}
      {excludedAdSpend > 0 && (
        <div
          className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3.5 text-xs text-amber-200"
          data-testid="excluded-spend-banner"
        >
          <div className="flex items-start gap-2.5">
            <AlertCircle size={16} className="shrink-0 mt-0.5 text-amber-400" />
            <div>
              <p className="font-semibold text-amber-100">
                Currency Mismatch: {fmtCurrency(excludedAdSpend, cur)} Ad Spend Excluded
              </p>
              <p className="text-amber-200/80 mt-0.5">
                Spend from connected accounts with mismatched currencies is excluded from financial totals to prevent inaccurate profit numbers without unverified FX conversion.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Existing COGS Banners */}
      {p.cogs_kind === "ESTIMATED" && (
        <div
          className="flex flex-col gap-3 rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 sm:flex-row sm:items-center sm:justify-between"
          data-testid="cogs-estimated-banner"
        >
          <div className="flex items-start gap-3">
            <AlertCircle size={18} className="mt-0.5 shrink-0 text-amber-400" />
            <div>
              <p className="text-sm font-semibold text-[#F8FAFC]">Unit Costs Partially Configured or Missing</p>
              <p className="text-xs text-[#CBD5E1]">
                COGS is missing for some products. True Profit currently reflects pre-COGS gross contribution.
              </p>
            </div>
          </div>
          <Button
            size="sm"
            onClick={() => navigate("/app/settings")}
            className="shrink-0 bg-amber-500 text-xs font-semibold text-amber-950 hover:bg-amber-400"
            data-testid="configure-cogs-btn"
          >
            Configure COGS in Settings
          </Button>
        </div>
      )}

      {p.cogs_kind === "CONFIGURED" && (
        <div
          className="flex items-center gap-2.5 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-xs text-emerald-300"
          data-testid="cogs-configured-banner"
        >
          <CheckCircle2 size={16} className="shrink-0 text-emerald-400" />
          <span>All product costs are configured by merchant. Net True Profit and Waterfall steps are computed with 100% merchant COGS.</span>
        </div>
      )}

      {p.cogs_kind === "IMPORTED" && (
        <div
          className="flex items-center gap-2.5 rounded-xl border border-sky-500/30 bg-sky-500/10 px-4 py-3 text-xs text-sky-300"
          data-testid="cogs-imported-banner"
        >
          <CheckCircle2 size={16} className="shrink-0 text-sky-400" />
          <span>Product costs were imported directly from Shopify variant inventory data. You can override them anytime in Settings.</span>
        </div>
      )}

      {/* Top 4 KPI Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="p-5">
          <Stat label="Gross Revenue" value={fmtCurrency(p.gross_revenue, cur)} />
        </Card>
        <Card className="p-5">
          <Stat label="Gross Profit" value={fmtCurrency(p.gross_profit, cur)} sub="after unit COGS" />
        </Card>
        <Card className="p-5">
          <Stat label="Contribution Margin" value={fmtCurrency(p.contribution_margin, cur)} sub="after direct marketing spend" />
        </Card>
        <Card className="border-emerald-500/30 bg-[#0B1A13] p-5">
          <Stat label="True Net Profit" value={fmtCurrency(p.true_profit, cur)} sub={`${fmtPercent(p.margin)} net operating margin`} />
        </Card>
      </div>

      {/* Waterfall Card */}
      <Card className="p-5 sm:p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <SectionHeader
            title="Profit Reconciliation Waterfall"
            subtitle="Step-by-step audit of gross revenue down to true net profit"
          />
          {eligibleAdSpend > 0 && (
            <span className="rounded border border-[#16221B] bg-[#070C0A] px-2.5 py-1 text-xs text-[#94A3B8]">
              Deducted Ad Spend: <strong className="text-[#F8FAFC]">{fmtCurrency(eligibleAdSpend, cur)}</strong>
            </span>
          )}
        </div>
        <div className="mt-6 space-y-3">
          {p.steps && p.steps.map((s, i) => {
            const isResult = s.type === "result";
            const isTotal = s.type === "total";
            const isAdSpend = s.label?.includes("Advertising");
            const pct = gross > 0 ? Math.min(100, (Math.abs(s.value) / gross) * 100) : 0;
            const color = isResult
              ? "#00E599"
              : isTotal
              ? "#38BDF8"
              : isAdSpend
              ? "#F59E0B"
              : "#F43F5E";

            return (
              <div key={i} className="flex items-center gap-2 sm:gap-3">
                <div className="w-28 sm:w-48 shrink-0 text-xs font-medium text-[#CBD5E1] flex items-center gap-1.5">
                  <span className="truncate">{s.label}</span>
                  {isAdSpend && (
                    <span className="text-[9px] sm:text-[10px] uppercase font-semibold text-amber-400 bg-amber-500/10 px-1 py-0.2 rounded border border-amber-500/20">
                      Ads
                    </span>
                  )}
                </div>
                <div className="flex-1 min-w-[50px]">
                  <div className="h-6 overflow-hidden rounded bg-[#070C0A] border border-[#16221B]">
                    <div
                      className="flex h-full items-center rounded px-2 text-[11px] font-semibold text-black transition-all"
                      style={{
                        width: `${Math.max(pct, s.value === 0 ? 0 : 4)}%`,
                        background: color,
                        opacity: isResult || isTotal ? 1 : 0.75,
                      }}
                    />
                  </div>
                </div>
                <div
                  className={`w-20 sm:w-32 shrink-0 text-right font-metric text-[11px] sm:text-xs font-bold ${
                    isResult
                      ? "text-emerald-400"
                      : isTotal
                      ? "text-sky-400"
                      : isAdSpend
                      ? "text-amber-300"
                      : "text-rose-300"
                  }`}
                >
                  {s.value < 0 ? "-" : ""}
                  {fmtCurrency(Math.abs(s.value), cur)}
                </div>
              </div>
            );
          })}
        </div>
      </Card>

      {/* Mismatch insight */}
      {p.insight && p.insight.mismatch && (
        <div className="rounded-xl border border-emerald-500/30 bg-[#0B1A13] p-5">
          <div className="flex items-start gap-3">
            <TrendingUp size={18} className="mt-0.5 shrink-0 text-emerald-400" />
            <div>
              <h3 className="font-display text-sm font-bold text-[#F8FAFC]">
                Volume vs. Profit Asymmetry Identified
              </h3>
              <p className="mt-1 text-xs leading-relaxed text-[#94A3B8]">
                <span className="font-semibold text-[#CBD5E1]">{p.insight.best_seller}</span> accounts for the highest unit volume, but{" "}
                <span className="font-semibold text-emerald-400">{p.insight.most_profitable}</span> delivers the highest net true profit.
                The best margin product is <span className="font-semibold text-emerald-400">{p.insight.best_margin}</span>.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Product Profitability */}
      <div className="rounded-xl border border-[#16221B] bg-[#0B110E] overflow-hidden">
        <div className="border-b border-[#16221B] bg-[#070C0A] p-5">
          <SectionHeader title="Product-Level Margin Matrix" subtitle="Ranked by total net true profit contribution" />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs" data-testid="product-profit-table">
            <thead>
              <tr className="border-b border-[#16221B] text-left uppercase tracking-wider text-[#64748B]">
                <th className="px-5 py-3 font-semibold">Product</th>
                <th className="px-5 py-3 text-right font-semibold">Units Sold</th>
                <th className="px-5 py-3 text-right font-semibold">Gross Revenue</th>
                <th className="px-5 py-3 text-right font-semibold">True Profit</th>
                <th className="px-5 py-3 text-right font-semibold">Net Margin</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#121A15]">
              {p.product_profit && p.product_profit.map((row, i) => (
                <tr key={i} className="hover:bg-[#0E1713] transition-colors">
                  <td className="px-5 py-3.5 font-medium text-[#F8FAFC]">{row.name}</td>
                  <td className="px-5 py-3.5 text-right font-metric text-[#CBD5E1]">{fmtNumber(row.units)}</td>
                  <td className="px-5 py-3.5 text-right font-metric text-[#CBD5E1]">{fmtCurrency(row.revenue, cur)}</td>
                  <td className="px-5 py-3.5 text-right font-metric font-bold text-emerald-400">{fmtCurrency(row.true_profit, cur)}</td>
                  <td className="px-5 py-3.5 text-right">
                    <span className={`font-metric font-bold ${row.margin > 20 ? "text-emerald-400" : row.margin > 10 ? "text-amber-400" : "text-rose-400"}`}>
                      {fmtPercent(row.margin)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
