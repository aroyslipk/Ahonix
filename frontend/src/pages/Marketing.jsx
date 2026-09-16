import React from "react";
import { useNavigate } from "react-router-dom";
import {
  Target,
  Zap,
  MousePointerClick,
  Eye,
  ShoppingCart,
  DollarSign,
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Plug,
  ArrowRight,
  TrendingUp,
  Layers,
  HelpCircle,
} from "lucide-react";
import { useSection } from "@/lib/hooks";
import { PageSkeleton, ErrorState, EmptyState } from "@/components/StateViews";
import { EmptyWorkspace } from "@/pages/Overview";
import { Card, SectionHeader, Stat } from "@/components/primitives";
import { fmtCurrency, fmtNumber } from "@/lib/api";
import { ValueBadge } from "@/components/ValueBadge";
import { Button } from "@/components/ui/button";

export default function Marketing() {
  const navigate = useNavigate();
  const { data, isLoading, isError, refetch } = useSection("marketing", "/marketing");

  if (isLoading) return <PageSkeleton />;
  if (isError) return <ErrorState onRetry={refetch} />;
  if (data?.empty) return <EmptyWorkspace name={data.workspace?.name} />;

  const cur = data.workspace?.currency || "USD";
  const m = data.marketing || {};
  const isDemo = Boolean(data.workspace?.is_demo);

  // Check whether any ad channel is connected
  const hasConnectedPlatforms =
    isDemo ||
    (m.by_platform && m.by_platform.length > 0) ||
    (m.campaigns && m.campaigns.length > 0) ||
    (m.currency_mismatches && m.currency_mismatches.length > 0);

  // 1. Strong Empty State when no real ad channels are connected
  if (!hasConnectedPlatforms) {
    return (
      <div className="space-y-8" data-testid="marketing-empty-state">
        <SectionHeader
          title="Marketing Intelligence"
          subtitle="ROAS is not profit. See revenue efficiency vs profit efficiency."
          icon={Target}
        />

        <div className="rounded-xl border border-[#16221B] bg-[#0B110E] p-8 sm:p-12 text-center max-w-2xl mx-auto shadow-xl">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl border border-emerald-500/20 bg-emerald-500/10 text-emerald-400 mb-5">
            <Plug size={28} />
          </div>

          <h2 className="text-xl font-bold text-[#F8FAFC]">
            No ad channels connected
          </h2>

          <p className="mt-2.5 text-xs text-[#94A3B8] leading-relaxed">
            Connect Meta Ads or Google Ads in Settings to view real advertising spend,
            blended ROAS, blended CAC, and campaign performance.
          </p>

          <div className="mt-4 inline-flex items-center gap-2 rounded-lg border border-[#16221B] bg-[#070C0A] px-3.5 py-2 text-xs text-[#CBD5E1]">
            <CheckCircle2 size={14} className="text-emerald-400 shrink-0" />
            <span>AHONIX never fabricates mock marketing metrics. Only verified ad spend is blended.</span>
          </div>

          <div className="mt-8 flex justify-center">
            <Button
              onClick={() => navigate("/app/settings")}
              className="bg-emerald-500 font-semibold text-emerald-950 hover:bg-emerald-400"
              data-testid="connect-ad-channels-btn"
            >
              Connect Ad Channels in Settings
              <ArrowRight size={15} className="ml-2" />
            </Button>
          </div>
        </div>
      </div>
    );
  }

  // 2. Connected State with Real Marketing Blending
  const metaPlatform = m.by_platform?.find(
    (p) => p.platform === "Meta Ads" || p.platform === "meta"
  );
  const googlePlatform = m.by_platform?.find(
    (p) => p.platform === "Google Ads" || p.platform === "google_ads"
  );

  const metaSpend = metaPlatform?.spend ?? 0.0;
  const googleSpend = googlePlatform?.spend ?? 0.0;

  const completeness = m.financial_completeness || { status: "PARTIAL", reasons: [] };
  const completenessStatus = completeness.status || "PARTIAL";
  const completenessReasons = completeness.reasons || [];

  const coverage = m.attribution_coverage || {
    coverage_pct: 0,
    attributed_orders_count: 0,
    total_orders_count: 0,
    status: "UNAVAILABLE",
  };

  const excludedSpend = m.excluded_ad_spend || 0.0;
  const eligibleSpend = m.eligible_ad_spend || 0.0;

  return (
    <div className="space-y-8" data-testid="marketing-connected-view">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <SectionHeader
          title="Marketing Intelligence"
          subtitle="Real advertising spend blended with Shopify ground truth revenue and merchant COGS."
          icon={Target}
        />
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-xs text-[#64748B]">Financial Completeness:</span>
          <span
            className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide border ${
              completenessStatus === "FULL"
                ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                : completenessStatus === "PARTIAL"
                ? "border-amber-500/30 bg-amber-500/10 text-amber-300"
                : "border-[#16221B] bg-[#070C0A] text-[#94A3B8]"
            }`}
            data-testid="marketing-completeness-badge"
          >
            {completenessStatus === "FULL" && <CheckCircle2 size={12} className="text-emerald-400" />}
            {completenessStatus === "PARTIAL" && <AlertTriangle size={12} className="text-amber-400" />}
            {completenessStatus}
          </span>
        </div>
      </div>

      {/* Financial Completeness Explanation Banner */}
      {completenessStatus !== "FULL" && completenessReasons.length > 0 && (
        <div
          className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-xs text-amber-200"
          data-testid="completeness-reasons-banner"
        >
          <div className="flex items-start gap-2.5">
            <AlertTriangle size={16} className="shrink-0 mt-0.5 text-amber-400" />
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

      {/* Currency Mismatch Alert Banner */}
      {excludedSpend > 0 && (
        <div
          className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-xs text-amber-200"
          data-testid="excluded-spend-banner"
        >
          <div className="flex items-start gap-2.5">
            <AlertCircle size={16} className="shrink-0 mt-0.5 text-amber-400" />
            <div>
              <p className="font-semibold text-amber-100">
                Excluded Ad Spend: {fmtCurrency(excludedSpend, cur)}
              </p>
              <p className="text-amber-200/80 mt-0.5 leading-relaxed">
                Spend from connected ad accounts with mismatched currencies was excluded from
                financial totals to maintain mathematical integrity without unverified FX conversion.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Top Metrics Cards */}
      <div className="grid grid-cols-1 gap-3 sm:gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="p-4 sm:p-5">
          <Stat
            label="Eligible Ad Spend"
            value={fmtCurrency(eligibleSpend, cur)}
            sub="flows into True Profit"
          />
        </Card>
        <Card className="p-4 sm:p-5">
          <Stat
            label="Excluded Ad Spend"
            value={fmtCurrency(excludedSpend, cur)}
            sub={excludedSpend > 0 ? "Currency mismatch" : "No exclusions"}
          />
        </Card>
        <Card className="p-4 sm:p-5">
          <Stat
            label="Blended ROAS"
            value={eligibleSpend > 0 ? `${m.blended_roas}x` : "—"}
            sub={eligibleSpend > 0 ? "gross revenue ÷ ad spend" : "No eligible spend"}
          />
        </Card>
        <Card className="p-4 sm:p-5">
          <Stat
            label="Blended CAC"
            value={eligibleSpend > 0 ? fmtCurrency(m.blended_cac, cur) : "—"}
            sub={eligibleSpend > 0 ? "ad spend ÷ orders" : "No eligible spend"}
          />
        </Card>
      </div>

      {/* Channel Spend & Attribution Overview */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="p-4 bg-[#0B110E]">
          <div className="flex items-center justify-between text-xs text-[#94A3B8]">
            <span>Meta Ads Spend</span>
            <span className="rounded bg-[#070C0A] border border-[#16221B] px-1.5 py-0.5 text-[10px] text-[#CBD5E1]">
              {metaPlatform ? "Connected" : "Inactive"}
            </span>
          </div>
          <p className="mt-2 font-metric text-xl font-bold text-[#F8FAFC]">
            {fmtCurrency(metaSpend, cur)}
          </p>
        </Card>

        <Card className="p-4 bg-[#0B110E]">
          <div className="flex items-center justify-between text-xs text-[#94A3B8]">
            <span>Google Ads Spend</span>
            <span className="rounded bg-[#070C0A] border border-[#16221B] px-1.5 py-0.5 text-[10px] text-[#CBD5E1]">
              {googlePlatform ? "Connected" : "Inactive"}
            </span>
          </div>
          <p className="mt-2 font-metric text-xl font-bold text-[#F8FAFC]">
            {fmtCurrency(googleSpend, cur)}
          </p>
        </Card>

        <Card className="p-4 bg-[#0B110E]">
          <div className="flex items-center justify-between text-xs text-[#94A3B8]">
            <span>Attributed Revenue</span>
            <span className="rounded bg-emerald-500/10 px-1.5 py-0.5 text-[10px] text-emerald-400 border border-emerald-500/20">
              ATTRIBUTED
            </span>
          </div>
          <p className="mt-2 font-metric text-xl font-bold text-emerald-400">
            {coverage.attributed_orders_count > 0
              ? fmtCurrency(m.attributed_revenue, cur)
              : "—"}
          </p>
          <p className="mt-1 text-[11px] text-[#64748B]">
            {coverage.attributed_orders_count > 0
              ? `${m.attributed_roas}x Attributed ROAS`
              : "Attribution unavailable"}
          </p>
        </Card>

        <Card className="p-4 bg-[#0B110E]">
          <div className="flex items-center justify-between text-xs text-[#94A3B8]">
            <span>Attribution Coverage</span>
            <span className="text-[11px] text-[#64748B] font-metric">
              {coverage.attributed_orders_count} / {coverage.total_orders_count} orders
            </span>
          </div>
          <p className="mt-2 font-metric text-xl font-bold text-[#F8FAFC]">
            {coverage.coverage_pct}%
          </p>
          <p className="mt-1 text-[11px] text-[#64748B]">
            Orders with verified campaign UTMs
          </p>
        </Card>
      </div>

      {/* Paradox / Insight */}
      {m.paradox && m.paradox.high_roas_campaign && m.paradox.high_profit_campaign && (
        <Card className="border-l-4 border-l-emerald-500 bg-[#0B1A13] p-5">
          <div className="flex items-start gap-3">
            <Zap size={18} className="mt-0.5 text-emerald-400 shrink-0" />
            <div>
              <h3 className="font-display text-base font-bold text-[#F8FAFC]">
                Highest ROAS ≠ most profit
              </h3>
              <p className="mt-1 text-xs text-[#94A3B8] leading-relaxed">
                <span className="font-semibold text-[#CBD5E1]">{m.paradox.high_roas_campaign}</span>{" "}
                has the best ROAS, but{" "}
                <span className="font-semibold text-emerald-400">{m.paradox.high_profit_campaign}</span>{" "}
                contributes more real profit after COGS and fees. Optimize for contribution, not ROAS alone.
              </p>
            </div>
          </div>
        </Card>
      )}

      {/* Campaign Performance Table */}
      <Card className="overflow-hidden">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between border-b border-[#16221B] bg-[#070C0A] p-5 gap-2">
          <div>
            <h3 className="font-display text-base font-bold text-[#F8FAFC]">
              Campaign Performance & Attribution
            </h3>
            <p className="text-xs text-[#64748B] mt-0.5">
              Distinguishing platform-reported metrics from verified first-party Shopify order attribution
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center rounded bg-[#0B110E] px-2 py-0.5 text-[10px] font-semibold text-[#94A3B8] border border-[#16221B]">
              IMPORTED = Ad Platform
            </span>
            <span className="inline-flex items-center rounded bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-400 border border-emerald-500/20">
              ATTRIBUTED = Shopify
            </span>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-xs" data-testid="campaign-table">
            <thead>
              <tr className="border-b border-[#16221B] text-left uppercase tracking-wider text-[#64748B] bg-[#070C0A]">
                <th className="px-4 py-3 font-semibold">Platform</th>
                <th className="px-4 py-3 font-semibold">Campaign</th>
                <th className="px-4 py-3 text-right font-semibold">Spend</th>
                <th className="px-4 py-3 text-right font-semibold">
                  Impr. <span className="text-[10px] text-[#475569] font-normal">(IMP)</span>
                </th>
                <th className="px-4 py-3 text-right font-semibold">
                  Clicks <span className="text-[10px] text-[#475569] font-normal">(IMP)</span>
                </th>
                <th className="px-4 py-3 text-right font-semibold">
                  Conv. <span className="text-[10px] text-[#475569] font-normal">(IMP)</span>
                </th>
                <th className="px-4 py-3 text-right font-semibold">
                  Orders <span className="text-[10px] text-emerald-400 font-normal">(ATTR)</span>
                </th>
                <th className="px-4 py-3 text-right font-semibold">
                  Revenue <span className="text-[10px] text-emerald-400 font-normal">(ATTR)</span>
                </th>
                <th className="px-4 py-3 text-right font-semibold">
                  Contribution <span className="text-[10px] text-emerald-400 font-normal">(ATTR)</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#121A15]">
              {m.campaigns && m.campaigns.length > 0 ? (
                m.campaigns.map((c, i) => {
                  const hasAttr = c.attribution_status === "ATTRIBUTED" && c.attributed_revenue != null;
                  const isPositiveContribution = (c.attributed_contribution ?? 0) >= 0;

                  return (
                    <tr
                      key={c.id || i}
                      className="hover:bg-[#0E1713] transition-colors"
                      data-testid={`campaign-row-${c.id || i}`}
                    >
                      {/* Platform */}
                      <td className="px-4 py-3 text-xs text-[#CBD5E1]">
                        <span className="inline-flex items-center rounded bg-[#070C0A] px-2 py-0.5 text-[11px] font-medium text-[#CBD5E1] border border-[#16221B]">
                          {c.platform}
                        </span>
                      </td>

                      {/* Campaign Name */}
                      <td className="px-4 py-3">
                        <p className="font-medium text-xs text-[#F8FAFC] max-w-[200px] truncate" title={c.name}>
                          {c.name}
                        </p>
                        <p className="text-[10px] text-[#64748B] font-mono mt-0.5">
                          ID: {c.id}
                        </p>
                      </td>

                      {/* Spend */}
                      <td className="px-4 py-3 text-right font-metric text-xs font-semibold text-[#CBD5E1]">
                        {fmtCurrency(c.spend, cur)}
                      </td>

                      {/* Impressions (Imported) */}
                      <td className="px-4 py-3 text-right font-metric text-xs text-[#94A3B8]">
                        {fmtNumber(c.impressions)}
                      </td>

                      {/* Clicks (Imported) */}
                      <td className="px-4 py-3 text-right font-metric text-xs text-[#94A3B8]">
                        {fmtNumber(c.clicks)}
                      </td>

                      {/* Imported Conversions */}
                      <td className="px-4 py-3 text-right font-metric text-xs text-[#94A3B8]">
                        {fmtNumber(c.imported_conversions)}
                      </td>

                      {/* Attributed Orders */}
                      <td className="px-4 py-3 text-right font-metric text-xs">
                        {hasAttr ? (
                          <span className="font-semibold text-[#CBD5E1]">
                            {c.attributed_orders_count}
                          </span>
                        ) : (
                          <span className="text-[#64748B]">—</span>
                        )}
                      </td>

                      {/* Attributed Revenue */}
                      <td className="px-4 py-3 text-right font-metric text-xs">
                        {hasAttr ? (
                          <span className="font-semibold text-emerald-400">
                            {fmtCurrency(c.attributed_revenue, cur)}
                          </span>
                        ) : (
                          <span className="text-[11px] text-[#64748B] italic">
                            Attribution unavailable
                          </span>
                        )}
                      </td>

                      {/* Attributed Contribution */}
                      <td className="px-4 py-3 text-right font-metric text-xs">
                        {hasAttr ? (
                          <span
                            className={`font-semibold ${
                              isPositiveContribution ? "text-emerald-400" : "text-rose-400"
                            }`}
                          >
                            {c.attributed_contribution < 0 ? "-" : "+"}
                            {fmtCurrency(Math.abs(c.attributed_contribution), cur)}
                          </span>
                        ) : (
                          <span className="text-[11px] text-[#64748B] italic">
                            Attribution unavailable
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={9} className="px-4 py-8 text-center text-xs text-[#64748B]">
                    No campaigns synced in this 28-day reporting window.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Legend / Guidance Note */}
        <div className="border-t border-[#16221B] bg-[#070C0A] px-5 py-3 text-[11px] text-[#64748B] flex flex-wrap items-center justify-between gap-2">
          <span>
            <strong>Attributed Campaign Contribution</strong> = Attributed Revenue − Attributed COGS − Ad Spend.
          </span>
          <span>
            When first-party UTM matches do not exist for an order, attribution is marked <em>unavailable</em> rather than guessing.
          </span>
        </div>
      </Card>
    </div>
  );
}

