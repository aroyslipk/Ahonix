import React from "react";
import { useNavigate } from "react-router-dom";
import { Package, ArrowRight } from "lucide-react";
import { useSection } from "@/lib/hooks";
import { PageSkeleton, ErrorState } from "@/components/StateViews";
import { EmptyWorkspace } from "@/pages/Overview";
import { SectionHeader } from "@/components/primitives";
import { ValueBadge } from "@/components/ValueBadge";
import { fmtCurrency, fmtNumber } from "@/lib/api";

export function HealthRing({ score, size = 48 }) {
  const r = (size - 6) / 2;
  const c = 2 * Math.PI * r;
  const color = score >= 75 ? "#00E599" : score >= 55 ? "#F59E0B" : "#F43F5E";
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#16221B" strokeWidth="4" />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth="4" strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={c - (score / 100) * c} />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center font-metric text-xs font-bold" style={{ color }}>
        {score}
      </span>
    </div>
  );
}

export default function Products() {
  const navigate = useNavigate();
  const { data, isLoading, isError, refetch } = useSection("products", "/products");
  if (isLoading) return <PageSkeleton />;
  if (isError) return <ErrorState onRetry={refetch} />;
  if (data?.empty) return <EmptyWorkspace name={data.workspace?.name} />;

  const cur = data?.workspace?.currency || "USD";
  const products = data?.products || [];
  const isDemo = Boolean(data?.workspace?.is_demo);

  if (!isDemo && products.length === 0) {
    return (
      <div className="space-y-8" data-testid="products-empty-state">
        <SectionHeader
          title="Product Intelligence"
          subtitle="Multidimensional catalog ranking across velocity, unit margins, and return friction"
          icon={Package}
        />
        <EmptyWorkspace
          name={data?.workspace?.name}
          title="No products in catalog yet"
          description="Connect your Shopify store in Settings to automatically sync catalog SKUs, unit economics, COGS, and return friction."
        />
      </div>
    );
  }

  return (
    <div className="space-y-8" data-testid="products-page">
      <SectionHeader
        title="Product Intelligence"
        subtitle="Multidimensional catalog ranking across velocity, unit margins, and return friction"
        icon={Package}
      />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {products.map((p) => (
          <button
            key={p.id}
            onClick={() => navigate(`/app/products/${p.id}`)}
            className="rounded-xl border border-[#16221B] bg-[#0B110E] p-5 text-left transition-all duration-200 hover:border-emerald-500/30 hover:bg-[#0E1713]"
            data-testid={`product-card-${p.id}`}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <p className="truncate font-display font-bold text-[#F8FAFC]">{p.name || "Untitled Product"}</p>
                  {p.cogs_status && <ValueBadge kind={p.cogs_status} />}
                </div>
                <p className="mt-0.5 text-xs text-[#64748B]">{p.category || "General"} · {p.channel || "Direct"}</p>
              </div>
              <HealthRing score={p.health?.score ?? 50} />
            </div>
            <div className="mt-4 grid grid-cols-3 gap-2 rounded-lg border border-[#16221B] bg-[#070C0A] p-2.5 text-center">
              <div><p className="text-[10px] uppercase tracking-wider text-[#64748B]">Revenue</p><p className="mt-0.5 font-metric text-xs font-bold text-[#F8FAFC]">{fmtCurrency(p.revenue || 0, cur, true)}</p></div>
              <div><p className="text-[10px] uppercase tracking-wider text-[#64748B]">Margin</p><p className={`mt-0.5 font-metric text-xs font-bold ${(p.margin || 0) > 20 ? "text-emerald-400" : "text-amber-400"}`}>{p.margin || 0}%</p></div>
              <div><p className="text-[10px] uppercase tracking-wider text-[#64748B]">Returns</p><p className="mt-0.5 font-metric text-xs font-bold text-[#CBD5E1]">{p.return_rate || 0}%</p></div>
            </div>
            <div className="mt-3 flex items-center justify-between border-t border-[#16221B] pt-3">
              <span className="text-xs text-[#64748B]">{fmtNumber(p.units || 0)} units sold</span>
              <span className="flex items-center gap-1 text-xs font-medium text-emerald-400">Inspect SKU <ArrowRight size={12} /></span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

