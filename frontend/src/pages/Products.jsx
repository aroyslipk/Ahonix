import React from "react";
import { useNavigate } from "react-router-dom";
import { Package, ArrowRight } from "lucide-react";
import { useSection } from "@/lib/hooks";
import { PageSkeleton, ErrorState } from "@/components/StateViews";
import { EmptyWorkspace } from "@/pages/Overview";
import { Card, SectionHeader } from "@/components/primitives";
import { ValueBadge } from "@/components/ValueBadge";
import { fmtCurrency, fmtNumber } from "@/lib/api";

export function HealthRing({ score, size = 48 }) {
  const r = (size - 6) / 2;
  const c = 2 * Math.PI * r;
  const color = score >= 75 ? "#10B981" : score >= 55 ? "#F59E0B" : "#F43F5E";
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#1E2235" strokeWidth="4" />
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

  const cur = data.workspace.currency;

  return (
    <div className="space-y-8">
      <SectionHeader
        title="Product Intelligence"
        subtitle="Every product scored across demand, profit, returns, inventory and marketing"
        icon={Package}
      />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {data.products.map((p) => (
          <button
            key={p.id}
            onClick={() => navigate(`/app/products/${p.id}`)}
            className="rounded-xl border border-[#1E2235] bg-[#121420] p-5 text-left card-hover"
            data-testid={`product-card-${p.id}`}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <p className="truncate font-display font-bold text-[#F8FAFC]">{p.name}</p>
                  {p.cogs_status && <ValueBadge kind={p.cogs_status} />}
                </div>
                <p className="text-xs text-[#64748B]">{p.category} · {p.channel}</p>
              </div>
              <HealthRing score={p.health.score} />
            </div>
            <div className="mt-4 grid grid-cols-3 gap-2 text-center">
              <div><p className="text-[10px] text-[#64748B]">Revenue</p><p className="font-metric text-sm font-bold text-[#F8FAFC]">{fmtCurrency(p.revenue, cur, true)}</p></div>
              <div><p className="text-[10px] text-[#64748B]">Margin</p><p className={`font-metric text-sm font-bold ${p.margin > 20 ? "text-emerald-400" : "text-amber-400"}`}>{p.margin}%</p></div>
              <div><p className="text-[10px] text-[#64748B]">Returns</p><p className="font-metric text-sm font-bold text-[#CBD5E1]">{p.return_rate}%</p></div>
            </div>
            <div className="mt-3 flex items-center justify-between border-t border-[#1E2235] pt-3">
              <span className="text-xs text-[#64748B]">{fmtNumber(p.units)} units sold</span>
              <span className="flex items-center gap-1 text-xs font-medium text-emerald-400">Details <ArrowRight size={12} /></span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
