import React from "react";
import { useNavigate, Link } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import {
  Settings as SettingsIcon,
  Plug,
  Check,
  LogOut,
  Building2,
  Loader2,
  Plus,
  RefreshCw,
  Unlink,
  AlertCircle,
  CheckCircle2,
  ExternalLink,
  Coins,
  ChevronDown,
  ChevronUp,
  Save,
  Search,
} from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { useWorkspace } from "@/context/WorkspaceContext";
import { Card, SectionHeader, Stat } from "@/components/primitives";
import { ValueBadge } from "@/components/ValueBadge";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { MarketingIntegrationCard } from "@/components/MarketingIntegrationCard";

const INTEGRATIONS = [
  { name: "Shopify", cat: "Store" },
  { name: "Amazon", cat: "Marketplace" },
  { name: "WooCommerce", cat: "Store" },
  { name: "Stripe", cat: "Payments" },
  { name: "Meta Ads", cat: "Marketing" },
  { name: "Google Ads", cat: "Marketing" },
  { name: "TikTok Ads", cat: "Marketing" },
  { name: "ShipStation", cat: "Logistics" },
];

function CogsSettingsCard({ workspace }) {
  const qc = useQueryClient();
  const [data, setData] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [savingId, setSavingId] = React.useState(null);
  const [search, setSearch] = React.useState("");
  const [expanded, setExpanded] = React.useState({});
  const [costs, setCosts] = React.useState({});

  const fetchCogs = React.useCallback(async () => {
    try {
      setLoading(true);
      const res = await api.get("/cogs");
      setData(res.data);
      const initial = {};
      (res.data?.products || []).forEach((p) => {
        const vMap = {};
        (p.variants || []).forEach((v) => {
          vMap[v.variant_id] = v.configured_cost ?? (v.imported_cost ?? "");
        });
        initial[p.product_id] = {
          unit_cost: p.configured_unit_cost ?? (p.unit_cost ?? ""),
          variants: vMap,
        };
      });
      setCosts(initial);
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    fetchCogs();
  }, [fetchCogs, workspace?.workspace_id]);

  const isDemo = data?.is_demo || workspace?.is_demo;

  const handleProductCostChange = (pid, val) => {
    setCosts((prev) => ({
      ...prev,
      [pid]: {
        ...prev[pid],
        unit_cost: val,
      },
    }));
  };

  const handleVariantCostChange = (pid, vid, val) => {
    setCosts((prev) => ({
      ...prev,
      [pid]: {
        ...prev[pid],
        variants: {
          ...(prev[pid]?.variants || {}),
          [vid]: val,
        },
      },
    }));
  };

  const handleSaveProduct = async (product) => {
    if (isDemo) return;
    const pid = product.product_id;
    const prodCosts = costs[pid] || {};
    setSavingId(pid);
    try {
      const variantsPayload = (product.variants || []).map((v) => ({
        variant_id: v.variant_id,
        title: v.title,
        sku: v.sku,
        unit_cost:
          prodCosts.variants?.[v.variant_id] !== "" && prodCosts.variants?.[v.variant_id] !== undefined
            ? parseFloat(prodCosts.variants[v.variant_id])
            : null,
      }));

      const payload = {
        unit_cost:
          prodCosts.unit_cost !== "" && prodCosts.unit_cost !== undefined
            ? parseFloat(prodCosts.unit_cost)
            : null,
        variants: variantsPayload,
      };

      await api.put(`/cogs/${pid}`, payload);
      toast.success(`COGS updated for "${product.title}".`);
      await qc.invalidateQueries();
      await fetchCogs();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to update COGS.");
    } finally {
      setSavingId(null);
    }
  };

  const toggleExpand = (pid) => {
    setExpanded((prev) => ({ ...prev, [pid]: !prev[pid] }));
  };

  const filtered = (data?.products || []).filter((p) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (
      p.title?.toLowerCase().includes(q) ||
      p.category?.toLowerCase().includes(q) ||
      String(p.product_id).includes(q)
    );
  });

  return (
    <Card className="p-6 border-[#16221B] bg-[#070C0A]" data-testid="cogs-settings-card">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <SectionHeader
          title="Product Costs & COGS (Unit Margins)"
          subtitle="Configure unit cost of goods sold per product or variant to unlock true net profit and accurate contribution margins."
          icon={Coins}
        />
        {data && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-xl bg-[#0B110E] border border-[#16221B] px-3 py-1.5 text-xs text-[#94A3B8]">
              Margin Coverage: <strong className="text-[#00E599] font-metric">{data.coverage_pct}%</strong>
            </span>
          </div>
        )}
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-10">
          <Loader2 className="animate-spin text-[#00E599]" size={24} />
        </div>
      ) : !data ? (
        <div className="py-6 text-center text-xs text-[#64748B]">Unable to load COGS configuration.</div>
      ) : (
        <div className="mt-6 space-y-4">
          {/* Summary stats */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <div className="rounded-xl border border-[#16221B] bg-[#0B110E] p-3.5">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-[#64748B]">Total SKUs</p>
              <p className="mt-1 font-metric text-lg font-bold text-[#F8FAFC]">{data.total_products}</p>
            </div>
            <div className="rounded-xl border border-[#16221B] bg-[#0B110E] p-3.5">
              <div className="flex items-center justify-between">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-[#64748B]">Merchant Configured</p>
                <ValueBadge kind="CONFIGURED" />
              </div>
              <p className="mt-1 font-metric text-lg font-bold text-[#00E599]">{data.configured_count}</p>
            </div>
            <div className="rounded-xl border border-[#16221B] bg-[#0B110E] p-3.5">
              <div className="flex items-center justify-between">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-[#64748B]">Shopify Imported</p>
                <ValueBadge kind="IMPORTED" />
              </div>
              <p className="mt-1 font-metric text-lg font-bold text-sky-400">{data.imported_count}</p>
            </div>
            <div className="rounded-xl border border-[#16221B] bg-[#0B110E] p-3.5">
              <div className="flex items-center justify-between">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-[#64748B]">Unconfigured ($0)</p>
                <ValueBadge kind="UNCONFIGURED" />
              </div>
              <p className="mt-1 font-metric text-lg font-bold text-rose-400">{data.unconfigured_count}</p>
            </div>
          </div>

          {isDemo && (
            <div className="rounded-xl border border-[#D4AF37]/30 bg-[#D4AF37]/10 p-3.5 text-xs text-[#F5DE87]">
              <strong className="text-[#F8FAFC]">Demo Mode:</strong> Northstar Goods benchmark COGS is active and locked. Connect a live Shopify store to configure real merchant unit costs.
            </div>
          )}

          {!isDemo && (
            <div className="rounded-xl border border-emerald-500/25 bg-emerald-500/5 p-3.5 text-xs text-[#00E599]">
              Merchant-configured unit cost takes precedence over Shopify-imported costs. If left unconfigured, COGS falls back to $0.00 and profit is labeled ESTIMATED.
            </div>
          )}

          {/* Search bar */}
          <div className="relative">
            <Search className="absolute left-3.5 top-3 text-[#64748B]" size={14} />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search products by title, SKU, or category..."
              className="w-full rounded-xl border border-[#16221B] bg-[#0B110E] pl-9 pr-3.5 py-2.5 text-xs text-[#F8FAFC] placeholder-[#64748B] focus:border-[#00E599] focus:outline-none"
              data-testid="cogs-search-input"
            />
          </div>

          {/* Product Items List */}
          {filtered.length === 0 ? (
            <div className="py-6 text-center text-xs text-[#64748B]">No matching products found.</div>
          ) : (
            <div className="space-y-3">
              {filtered.map((prod) => {
                const pid = prod.product_id;
                const prodCostState = costs[pid] || {};
                const isExpanded = !!expanded[pid];
                const hasVariants = (prod.variants || []).length > 1;

                return (
                  <div
                    key={pid}
                    className="rounded-xl border border-[#16221B] bg-[#0B110E] p-4 transition-all hover:border-[#1F3327]"
                    data-testid={`cogs-row-${pid}`}
                  >
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="font-semibold text-sm text-[#F8FAFC] truncate">{prod.title}</p>
                          <ValueBadge kind={prod.cogs_status || "UNCONFIGURED"} />
                        </div>
                        <p className="text-xs text-[#64748B] mt-1">
                          {prod.category} · Retail: <strong className="text-[#CBD5E1] font-metric">${(prod.min_price || 0).toFixed(2)}</strong> · Stock: <strong className="text-[#CBD5E1] font-metric">{prod.stock}</strong>
                          {prod.margin > 0 && <span> · Margin: <strong className="text-[#00E599] font-metric">{prod.margin}%</strong></span>}
                        </p>
                      </div>

                      <div className="flex flex-wrap items-center gap-2.5 shrink-0">
                        <div className="flex items-center gap-1.5">
                          <span className="text-xs text-[#64748B] font-medium">Unit Cost: $</span>
                          <input
                            type="number"
                            step="0.01"
                            min="0"
                            disabled={isDemo}
                            value={prodCostState.unit_cost ?? ""}
                            onChange={(e) => handleProductCostChange(pid, e.target.value)}
                            placeholder="0.00"
                            className="w-24 rounded-lg border border-[#16221B] bg-[#070C0A] px-2.5 py-1.5 text-xs text-[#F8FAFC] font-metric placeholder-[#64748B] focus:border-[#00E599] focus:outline-none disabled:opacity-50"
                            data-testid={`cogs-input-${pid}`}
                          />
                        </div>

                        {!isDemo && (
                          <Button
                            size="sm"
                            onClick={() => handleSaveProduct(prod)}
                            disabled={savingId === pid}
                            className="bg-[#00E599] text-xs font-bold text-[#040706] hover:bg-[#00c984] rounded-lg px-3 py-1.5"
                            data-testid={`save-cogs-${pid}`}
                          >
                            {savingId === pid ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} className="mr-1" />}
                            {savingId === pid ? "Saving..." : "Save"}
                          </Button>
                        )}

                        {hasVariants && (
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => toggleExpand(pid)}
                            className="text-xs text-[#94A3B8] hover:text-[#F8FAFC] hover:bg-[#121C16] rounded-lg"
                            data-testid={`expand-variants-${pid}`}
                          >
                            {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                            <span className="ml-1">{prod.variants.length} Variants</span>
                          </Button>
                        )}
                      </div>
                    </div>

                    {/* Variant Level breakdown */}
                    {hasVariants && isExpanded && (
                      <div className="mt-3.5 border-t border-[#16221B] pt-3.5" data-testid={`variants-table-${pid}`}>
                        <p className="text-[10px] font-semibold text-[#64748B] uppercase tracking-wider mb-2.5">
                          Variant-Specific Unit Costs (Overrides Product Base Cost)
                        </p>
                        <div className="space-y-2">
                          {prod.variants.map((v) => {
                            const vid = v.variant_id;
                            const varCostVal = prodCostState.variants?.[vid] ?? "";
                            return (
                              <div
                                key={vid}
                                className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 rounded-lg border border-[#16221B] bg-[#070C0A] px-3.5 py-2.5 text-xs"
                              >
                                <div className="flex items-center gap-2">
                                  <span className="text-[#F8FAFC] font-medium">{v.title}</span>
                                  {v.sku && <span className="text-[#64748B]">({v.sku})</span>}
                                  <ValueBadge kind={v.status || "UNCONFIGURED"} />
                                </div>
                                <div className="flex items-center gap-3">
                                  <span className="text-[#64748B]">Retail: ${v.price.toFixed(2)}</span>
                                  {v.imported_cost !== null && (
                                    <span className="text-sky-400/80">Shopify: ${v.imported_cost.toFixed(2)}</span>
                                  )}
                                  <div className="flex items-center gap-1.5">
                                    <span className="text-[#64748B]">Cost: $</span>
                                    <input
                                      type="number"
                                      step="0.01"
                                      min="0"
                                      disabled={isDemo}
                                      value={varCostVal}
                                      onChange={(e) => handleVariantCostChange(pid, vid, e.target.value)}
                                      placeholder="inherit"
                                      className="w-20 rounded-lg border border-[#16221B] bg-[#0B110E] px-2 py-1 text-xs text-[#F8FAFC] font-metric focus:border-[#00E599] focus:outline-none disabled:opacity-50"
                                      data-testid={`cogs-variant-input-${vid}`}
                                    />
                                  </div>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

export default function Settings() {
  const { user, logout } = useAuth();
  const { workspace, workspaces } = useWorkspace();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [creating, setCreating] = React.useState(false);
  const [switching, setSwitching] = React.useState(null);

  // Shopify integration state
  const [shopifyStatus, setShopifyStatus] = React.useState(null);
  const [shopifyLoading, setShopifyLoading] = React.useState(true);
  const [showShopifyInput, setShowShopifyInput] = React.useState(false);
  const [shopifyDomain, setShopifyDomain] = React.useState("");
  const [shopifyConnecting, setShopifyConnecting] = React.useState(false);
  const [shopifySyncing, setShopifySyncing] = React.useState(false);
  const [shopifyDisconnecting, setShopifyDisconnecting] = React.useState(false);

  // Meta Ads integration state
  const [metaStatus, setMetaStatus] = React.useState(null);
  const [metaLoading, setMetaLoading] = React.useState(true);
  const [metaAccounts, setMetaAccounts] = React.useState(null);
  const [metaAccountsLoading, setMetaAccountsLoading] = React.useState(false);

  // Google Ads integration state
  const [googleStatus, setGoogleStatus] = React.useState(null);
  const [googleLoading, setGoogleLoading] = React.useState(true);
  const [googleAccounts, setGoogleAccounts] = React.useState(null);
  const [googleAccountsLoading, setGoogleAccountsLoading] = React.useState(false);

  const fetchShopifyStatus = React.useCallback(async () => {
    try {
      const { data } = await api.get("/integrations/shopify/status");
      setShopifyStatus(data);
    } catch {
      setShopifyStatus({ connected: false });
    } finally {
      setShopifyLoading(false);
    }
  }, []);

  const fetchMetaStatus = React.useCallback(async () => {
    try {
      const { data } = await api.get("/integrations/meta/status");
      setMetaStatus(data);
    } catch {
      setMetaStatus({ connected: false });
    } finally {
      setMetaLoading(false);
    }
  }, []);

  const fetchMetaAccounts = React.useCallback(async () => {
    try {
      setMetaAccountsLoading(true);
      const { data } = await api.get("/integrations/meta/accounts");
      setMetaAccounts(data);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to fetch Meta ad accounts.");
    } finally {
      setMetaAccountsLoading(false);
    }
  }, []);

  const handleMetaConnect = async () => {
    try {
      const { data } = await api.post("/integrations/meta/connect");
      if (data?.authorization_url) {
        toast.info("Redirecting to Meta for authorization...");
        window.location.assign(data.authorization_url);
      }
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to initiate Meta Ads connection.");
    }
  };

  const handleMetaSync = async () => {
    try {
      const { data } = await api.post("/integrations/meta/sync", { days: 30 });
      toast.success(data?.detail || `Meta Ads insights synced: ${data?.synced_records_count || 0} records.`);
      await fetchMetaStatus();
      await qc.invalidateQueries({ queryKey: ["marketing"] });
      await qc.invalidateQueries({ queryKey: ["profit"] });
      await qc.invalidateQueries({ queryKey: ["overview"] });
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Meta Ads sync failed.");
      await fetchMetaStatus();
    }
  };

  const handleMetaSelectAccount = async (account) => {
    try {
      const accId = account.id || account.account_id;
      await api.post("/integrations/meta/select-account", {
        account_id: accId,
        account_name: account.name,
      });
      toast.success(`Selected Meta Ad Account: ${account.name || accId}`);
      await fetchMetaStatus();
      await fetchMetaAccounts();
      await qc.invalidateQueries({ queryKey: ["marketing"] });
      await qc.invalidateQueries({ queryKey: ["profit"] });
      await qc.invalidateQueries({ queryKey: ["overview"] });
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to select Meta ad account.");
    }
  };

  const handleMetaDisconnect = async () => {
    if (!window.confirm("Are you sure you want to disconnect Meta Ads from this workspace?")) return;
    try {
      await api.post("/integrations/meta/disconnect");
      toast.success("Meta Ads disconnected.");
      setMetaAccounts(null);
      await fetchMetaStatus();
      await qc.invalidateQueries({ queryKey: ["marketing"] });
      await qc.invalidateQueries({ queryKey: ["profit"] });
      await qc.invalidateQueries({ queryKey: ["overview"] });
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to disconnect Meta Ads.");
    }
  };

  const fetchGoogleStatus = React.useCallback(async () => {
    try {
      const { data } = await api.get("/integrations/google-ads/status");
      setGoogleStatus(data);
    } catch {
      setGoogleStatus({ connected: false });
    } finally {
      setGoogleLoading(false);
    }
  }, []);

  const fetchGoogleAccounts = React.useCallback(async () => {
    try {
      setGoogleAccountsLoading(true);
      const { data } = await api.get("/integrations/google-ads/accounts");
      setGoogleAccounts(data);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to fetch Google Ads accounts.");
    } finally {
      setGoogleAccountsLoading(false);
    }
  }, []);

  const handleGoogleConnect = async () => {
    try {
      const { data } = await api.post("/integrations/google-ads/connect");
      if (data?.authorization_url) {
        toast.info("Redirecting to Google for authorization...");
        window.location.assign(data.authorization_url);
      }
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to initiate Google Ads connection.");
    }
  };

  const handleGoogleSync = async () => {
    try {
      const { data } = await api.post("/integrations/google-ads/sync", { days: 30 });
      toast.success(data?.detail || `Google Ads insights synced: ${data?.synced_records_count || 0} records.`);
      await fetchGoogleStatus();
      await qc.invalidateQueries({ queryKey: ["marketing"] });
      await qc.invalidateQueries({ queryKey: ["profit"] });
      await qc.invalidateQueries({ queryKey: ["overview"] });
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Google Ads sync failed.");
      await fetchGoogleStatus();
    }
  };

  const handleGoogleSelectAccount = async (account) => {
    try {
      const cid = account.customer_id;
      await api.post("/integrations/google-ads/select-account", {
        customer_id: cid,
        account_name: account.display_name || account.name,
        login_customer_id: account.login_customer_id || (account.is_manager ? cid : null),
      });
      toast.success(`Selected Google Ads Account: ${account.display_name || cid}`);
      await fetchGoogleStatus();
      await fetchGoogleAccounts();
      await qc.invalidateQueries({ queryKey: ["marketing"] });
      await qc.invalidateQueries({ queryKey: ["profit"] });
      await qc.invalidateQueries({ queryKey: ["overview"] });
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to select Google Ads account.");
    }
  };

  const handleGoogleDisconnect = async () => {
    if (!window.confirm("Are you sure you want to disconnect Google Ads from this workspace?")) return;
    try {
      await api.post("/integrations/google-ads/disconnect");
      toast.success("Google Ads disconnected.");
      setGoogleAccounts(null);
      await fetchGoogleStatus();
      await qc.invalidateQueries({ queryKey: ["marketing"] });
      await qc.invalidateQueries({ queryKey: ["profit"] });
      await qc.invalidateQueries({ queryKey: ["overview"] });
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to disconnect Google Ads.");
    }
  };

  React.useEffect(() => {
    fetchShopifyStatus();
    fetchMetaStatus();
    fetchGoogleStatus();

    // Check for OAuth callback redirect parameters in query string
    const params = new URLSearchParams(window.location.search);
    let shouldClear = false;

    if (params.get("shopify") === "connected") {
      toast.success("Shopify store connected successfully!");
      fetchShopifyStatus();
      shouldClear = true;
    } else if (params.get("shopify_error")) {
      toast.error(`Shopify connection error: ${params.get("shopify_error")}`);
      shouldClear = true;
    }

    if (params.get("meta") === "connected") {
      toast.success("Meta Ads connected successfully! Please select your Ad Account.");
      fetchMetaStatus();
      fetchMetaAccounts();
      qc.invalidateQueries({ queryKey: ["marketing"] });
      qc.invalidateQueries({ queryKey: ["profit"] });
      qc.invalidateQueries({ queryKey: ["overview"] });
      shouldClear = true;
    } else if (params.get("meta_error")) {
      toast.error(`Meta Ads connection error: ${params.get("meta_error")}`);
      shouldClear = true;
    }

    if (params.get("google_ads") === "connected") {
      toast.success("Google Ads connected successfully! Please select your Customer Account.");
      fetchGoogleStatus();
      fetchGoogleAccounts();
      qc.invalidateQueries({ queryKey: ["marketing"] });
      qc.invalidateQueries({ queryKey: ["profit"] });
      qc.invalidateQueries({ queryKey: ["overview"] });
      shouldClear = true;
    } else if (params.get("google_ads_error")) {
      toast.error(`Google Ads connection error: ${params.get("google_ads_error")}`);
      shouldClear = true;
    }

    if (shouldClear) {
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }, [
    fetchShopifyStatus,
    fetchMetaStatus,
    fetchGoogleStatus,
    fetchMetaAccounts,
    fetchGoogleAccounts,
    qc,
    workspace?.workspace_id,
  ]);

  const handleShopifyConnect = async () => {
    if (!shopifyDomain.trim()) return;
    setShopifyConnecting(true);
    try {
      const { data } = await api.post("/integrations/shopify/connect", {
        shop: shopifyDomain.trim(),
      });
      if (data?.auth_url) {
        toast.info("Redirecting to Shopify for authorization...");
        window.location.assign(data.auth_url);
      }
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to initiate Shopify connection.");
      setShopifyConnecting(false);
    }
  };

  const handleShopifySync = async () => {
    setShopifySyncing(true);
    try {
      const { data } = await api.post("/integrations/shopify/sync");
      toast.success(`Sync complete: ${data?.summary?.product_count || 0} products, ${data?.summary?.order_count || 0} orders verified.`);
      await fetchShopifyStatus();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Shopify sync failed.");
      await fetchShopifyStatus();
    } finally {
      setShopifySyncing(false);
    }
  };

  const handleShopifyDisconnect = async () => {
    if (!window.confirm("Are you sure you want to disconnect Shopify from this workspace?")) return;
    setShopifyDisconnecting(true);
    try {
      await api.post("/integrations/shopify/disconnect");
      toast.success("Shopify disconnected.");
      setShowShopifyInput(false);
      setShopifyDomain("");
      await fetchShopifyStatus();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to disconnect Shopify.");
    } finally {
      setShopifyDisconnecting(false);
    }
  };

  const createDemo = async () => {
    setCreating(true);
    try {
      await api.post("/workspaces", { name: "Northstar Goods", mode: "demo", currency: "USD", channels: ["Shopify", "Amazon"] });
      await qc.invalidateQueries();
      toast.success("Demo workspace initialized.");
      navigate("/app/overview");
    } finally {
      setCreating(false);
    }
  };

  const switchTo = async (id) => {
    setSwitching(id);
    try {
      await api.post(`/workspaces/${id}/select`);
      await qc.invalidateQueries();
      toast.success("Workspace switched.");
      navigate("/app/overview");
    } finally {
      setSwitching(null);
    }
  };

  return (
    <div className="max-w-4xl space-y-8">
      <SectionHeader title="Settings & Integrations" subtitle="Workspace telemetry, data connections, and merchant account" icon={SettingsIcon} />

      {/* Current Workspace Info */}
      <Card className="p-6 border-[#16221B] bg-[#070C0A]">
        <SectionHeader title="Active Workspace" icon={Building2} />
        <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Stat label="Workspace Name" value={workspace?.name || "—"} />
          <Stat label="Operating Model" value={workspace?.business_type || "—"} />
          <Stat label="Functional Currency" value={workspace?.currency || "USD"} />
          <Stat label="Telemetry Mode" value={workspace?.is_demo ? "Demo Sandbox" : "Live Production"} />
        </div>
      </Card>

      {/* Workspaces Switcher */}
      <Card className="p-6 border-[#16221B] bg-[#070C0A]">
        <div className="flex items-center justify-between">
          <SectionHeader title="Available Workspaces" subtitle="Switch tenant or spin up a simulated sandbox" />
          <Button
            onClick={createDemo}
            disabled={creating}
            variant="outline"
            className="border-[#16221B] bg-[#0B110E] text-xs font-semibold text-[#F8FAFC] hover:bg-[#121C16] hover:border-[#1F3327] rounded-xl"
            data-testid="create-demo-btn"
          >
            {creating ? <Loader2 className="animate-spin" size={14} /> : <><Plus size={14} className="mr-1.5 text-[#00E599]" /> New Demo Workspace</>}
          </Button>
        </div>
        <div className="mt-4 space-y-2.5">
          {workspaces.map((w) => (
            <div
              key={w.workspace_id}
              className="flex items-center justify-between rounded-xl border border-[#16221B] bg-[#0B110E] px-4 py-3 transition-all hover:border-[#1F3327]"
            >
              <div className="flex items-center gap-3">
                <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-[#00E599]/30 bg-[#00E599]/15 text-xs font-bold text-[#00E599]">
                  {w.name.slice(0, 1)}
                </span>
                <div>
                  <p className="text-sm font-semibold text-[#F8FAFC]">{w.name}</p>
                  <p className="text-xs text-[#64748B]">{w.is_demo ? "Demo Sandbox" : "Live Production"}</p>
                </div>
              </div>
              {w.workspace_id === workspace?.workspace_id ? (
                <span className="flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-[11px] font-semibold text-[#00E599]">
                  <Check size={13} /> Active
                </span>
              ) : (
                <Button
                  size="sm"
                  onClick={() => switchTo(w.workspace_id)}
                  disabled={switching === w.workspace_id}
                  variant="ghost"
                  className="text-xs text-[#94A3B8] hover:bg-[#121C16] hover:text-[#F8FAFC] rounded-lg"
                >
                  {switching === w.workspace_id ? <Loader2 className="animate-spin" size={13} /> : "Switch"}
                </Button>
              )}
            </div>
          ))}
        </div>
      </Card>

      {/* Integrations Section */}
      <Card className="p-6 border-[#16221B] bg-[#070C0A]">
        <SectionHeader
          title="Integrations & Data Ingestion"
          subtitle="Connect live merchant data (Shopify live; Meta & Google Ads OAuth connected; other pipelines architecture-ready)"
          icon={Plug}
        />
        
        {/* Shopify Integration Card */}
        <div className="mt-5 rounded-xl border border-[#16221B] bg-[#0B110E] p-4 transition-all hover:border-[#1F3327]">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3.5">
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-500/10 text-[#00E599] border border-emerald-500/20 font-bold text-sm">
                S
              </span>
              <div>
                <div className="flex items-center gap-2">
                  <p className="text-sm font-semibold text-[#F8FAFC]">Shopify Storefront</p>
                  {shopifyLoading ? (
                    <Loader2 size={13} className="animate-spin text-[#64748B]" />
                  ) : shopifyStatus?.connected ? (
                    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-[11px] font-medium text-[#00E599] border border-emerald-500/20" data-testid="shopify-connected-badge">
                      <CheckCircle2 size={11} /> Connected
                    </span>
                  ) : (
                    <span className="rounded-full bg-[#121C16] border border-[#16221B] px-2 py-0.5 text-[11px] text-[#64748B]">
                      Storefront
                    </span>
                  )}
                </div>
                <p className="text-xs text-[#64748B] mt-0.5">
                  {shopifyStatus?.connected
                    ? `Store: ${shopifyStatus.shop} · API: ${shopifyStatus.api_version || "2026-07"}`
                    : "Connect your Shopify store to sync catalog, variant pricing, and orders (read-only)"}
                </p>
              </div>
            </div>

            {/* Action buttons */}
            <div className="flex items-center gap-2">
              {shopifyStatus?.connected ? (
                <>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleShopifySync}
                    disabled={shopifySyncing}
                    className="border-[#16221B] bg-[#121C16] text-xs font-semibold text-[#F8FAFC] hover:bg-[#16221B] rounded-lg"
                    data-testid="shopify-sync-btn"
                  >
                    <RefreshCw size={13} className={`mr-1.5 ${shopifySyncing ? "animate-spin text-[#00E599]" : ""}`} />
                    {shopifySyncing ? "Syncing..." : "Sync Now"}
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={handleShopifyDisconnect}
                    disabled={shopifyDisconnecting}
                    className="text-xs text-rose-400 hover:bg-rose-950/20 hover:text-rose-300 rounded-lg"
                    data-testid="shopify-disconnect-btn"
                  >
                    {shopifyDisconnecting ? <Loader2 size={13} className="animate-spin" /> : <><Unlink size={13} className="mr-1" /> Disconnect</>}
                  </Button>
                </>
              ) : (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setShowShopifyInput(!showShopifyInput)}
                  className="border-emerald-500/30 bg-emerald-500/10 text-xs font-semibold text-[#00E599] hover:bg-emerald-500/20 rounded-lg"
                  data-testid="connect-shopify"
                >
                  {showShopifyInput ? "Cancel" : "Connect Shopify"}
                </Button>
              )}
            </div>
          </div>

          {/* Connect Input Form */}
          {!shopifyStatus?.connected && showShopifyInput && (
            <div className="mt-4 rounded-xl border border-[#16221B] bg-[#070C0A] p-4" data-testid="shopify-connect-form">
              <p className="text-xs font-medium text-[#F8FAFC] mb-2">Enter your myshopify.com store domain:</p>
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                <div className="relative flex-1">
                  <input
                    type="text"
                    value={shopifyDomain}
                    onChange={(e) => setShopifyDomain(e.target.value)}
                    placeholder="your-store.myshopify.com"
                    className="w-full rounded-xl border border-[#16221B] bg-[#0B110E] px-3.5 py-2 text-xs text-[#F8FAFC] placeholder-[#64748B] focus:border-[#00E599] focus:outline-none"
                    data-testid="shopify-domain-input"
                  />
                </div>
                <Button
                  size="sm"
                  onClick={handleShopifyConnect}
                  disabled={shopifyConnecting || !shopifyDomain.trim()}
                  className="bg-[#00E599] text-xs font-bold text-[#040706] hover:bg-[#00c984] rounded-xl px-4 py-2"
                  data-testid="shopify-authorize-btn"
                >
                  {shopifyConnecting ? <Loader2 size={13} className="animate-spin mr-1.5" /> : <ExternalLink size={13} className="mr-1.5" />}
                  {shopifyConnecting ? "Redirecting..." : "Authorize on Shopify"}
                </Button>
              </div>
              <p className="mt-2 text-[11px] text-[#64748B]">
                Only read scopes (<code className="text-[#00E599]/80">read_products</code>, <code className="text-[#00E599]/80">read_orders</code>) are requested. AHONIX will never write to or modify your store.
              </p>
            </div>
          )}

          {/* Sync Status Subpanel */}
          {shopifyStatus?.connected && (
            <div className="mt-3.5 border-t border-[#16221B] pt-3 text-xs text-[#64748B]" data-testid="shopify-sync-status-panel">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-3">
                  <span>
                    Sync State:{" "}
                    <span className={`font-semibold ${
                      shopifyStatus.sync_status === "success"
                        ? "text-[#00E599]"
                        : shopifyStatus.sync_status === "failed"
                        ? "text-rose-400"
                        : shopifyStatus.sync_status === "syncing"
                        ? "text-cyan-400"
                        : "text-[#94A3B8]"
                    }`}>
                      {shopifyStatus.sync_status?.toUpperCase() || "IDLE"}
                    </span>
                  </span>
                  <span>·</span>
                  <span>
                    Last Ingested:{" "}
                    <span className="text-[#CBD5E1]">
                      {shopifyStatus.last_sync_at
                        ? new Date(shopifyStatus.last_sync_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
                        : "Never"}
                    </span>
                  </span>
                </div>

                {shopifyStatus.summary && (
                  <div className="flex items-center gap-2 text-[11px]">
                    <span className="rounded-lg bg-[#070C0A] px-2.5 py-1 text-[#94A3B8] border border-[#16221B]">
                      {shopifyStatus.summary.product_count} products verified
                    </span>
                    <span className="rounded-lg bg-[#070C0A] px-2.5 py-1 text-[#94A3B8] border border-[#16221B]">
                      {shopifyStatus.summary.order_count} orders verified
                    </span>
                  </div>
                )}
              </div>

              {shopifyStatus.sync_error && (
                <div className="mt-2.5 flex items-center gap-2 rounded-lg bg-rose-950/20 px-3 py-2 text-xs text-rose-300 border border-rose-900/30">
                  <AlertCircle size={14} className="shrink-0 text-rose-400" />
                  <span>Sync Error: {shopifyStatus.sync_error}</span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Meta Ads Integration Card */}
        <div className="mt-4">
          <MarketingIntegrationCard
            platform="meta"
            title="Meta Ads"
            description="Connect your Meta Ads account to ingest real daily campaign spend, impressions, clicks, ROAS, and CAC into True Profit."
            workspace={workspace}
            statusData={metaStatus}
            statusLoading={metaLoading}
            onConnect={handleMetaConnect}
            onDisconnect={handleMetaDisconnect}
            onSync={handleMetaSync}
            onSelectAccount={handleMetaSelectAccount}
            accountsData={metaAccounts}
            accountsLoading={metaAccountsLoading}
            onFetchAccounts={fetchMetaAccounts}
          />
        </div>

        {/* Google Ads Integration Card */}
        <div className="mt-4">
          <MarketingIntegrationCard
            platform="google_ads"
            title="Google Ads"
            description="Connect Google Ads with developer token support to sync daily campaign performance, search/shopping spend, and first-party UTM attribution."
            workspace={workspace}
            statusData={googleStatus}
            statusLoading={googleLoading}
            onConnect={handleGoogleConnect}
            onDisconnect={handleGoogleDisconnect}
            onSync={handleGoogleSync}
            onSelectAccount={handleGoogleSelectAccount}
            accountsData={googleAccounts}
            accountsLoading={googleAccountsLoading}
            onFetchAccounts={fetchGoogleAccounts}
          />
        </div>

        {/* Other integrations (architecture-ready) */}
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {INTEGRATIONS.filter((it) => !["Shopify", "Meta Ads", "Google Ads"].includes(it.name)).map((it) => (
            <div key={it.name} className="flex items-center justify-between rounded-xl border border-[#16221B] bg-[#0B110E] px-4 py-3 opacity-75">
              <div>
                <p className="text-sm font-semibold text-[#F8FAFC]">{it.name}</p>
                <p className="text-xs text-[#64748B]">{it.cat}</p>
              </div>
              <Button
                size="sm"
                variant="outline"
                onClick={() => toast.info(`${it.name} connector is ready in production pipeline.`)}
                className="border-[#16221B] bg-[#070C0A] text-xs text-[#94A3B8] hover:bg-[#121C16] hover:text-[#F8FAFC] rounded-lg"
                data-testid={`connect-${it.name.toLowerCase().replace(/\s/g, "-")}`}
              >
                Connect
              </Button>
            </div>
          ))}
        </div>
        <p className="mt-4 text-xs text-[#64748B]">
          Integrations are strictly decoupled and read-only. AHONIX connects via official OAuth 2.0 and never modifies external merchant data.
        </p>
      </Card>

      {/* Merchant COGS Configuration Card */}
      <CogsSettingsCard workspace={workspace} />

      {/* Account Section */}
      <Card className="p-6 border-[#16221B] bg-[#070C0A]">
        <SectionHeader title="Merchant Account" />
        <div className="mt-4 flex items-center justify-between">
          <div>
            <p className="text-sm font-semibold text-[#F8FAFC]">{user?.name}</p>
            <p className="text-xs text-[#64748B]">{user?.email} · Authenticated via {user?.auth_provider === "google" ? "Google OAuth" : "Email / Password"}</p>
          </div>
          <Button
            onClick={async () => { await logout(); navigate("/login"); }}
            variant="outline"
            className="border-rose-900/40 bg-rose-950/10 text-xs font-semibold text-rose-300 hover:bg-rose-950/20 rounded-xl"
            data-testid="settings-logout-btn"
          >
            <LogOut size={14} className="mr-1.5" /> Sign Out
          </Button>
        </div>
      </Card>

      {/* Legal & Policies Card */}
      <Card className="p-6 border-[#16221B] bg-[#070C0A]" data-testid="settings-legal-card">
        <SectionHeader title="Legal & Policies" />
        <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between text-xs text-[#94A3B8]">
          <p>
            Review our statutory compliance, data protection agreements, and merchant governance standards.
          </p>
          <div className="flex items-center gap-4">
            <Link
              to="/privacy"
              className="font-medium text-[#00E599] hover:text-[#00c984] hover:underline"
              data-testid="settings-privacy-link"
            >
              Privacy Policy
            </Link>
            <span className="text-[#16221B]">·</span>
            <Link
              to="/terms"
              className="font-medium text-[#00E599] hover:text-[#00c984] hover:underline"
              data-testid="settings-terms-link"
            >
              Terms of Service
            </Link>
          </div>
        </div>
      </Card>
    </div>
  );
}
