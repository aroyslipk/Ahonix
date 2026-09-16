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
  CreditCard,
  Sparkles,
  Shield,
  Zap,
  X,
  Trash2,
} from "lucide-react";
import { api, formatApiErrorDetail } from "@/lib/api";
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

  // Workspace management state
  const [showCreateWorkspaceModal, setShowCreateWorkspaceModal] = React.useState(false);
  const [newWorkspaceName, setNewWorkspaceName] = React.useState("");
  const [newWorkspaceType, setNewWorkspaceType] = React.useState("DTC Brand");
  const [newWorkspaceCurrency, setNewWorkspaceCurrency] = React.useState("USD");
  const [newWorkspaceMode, setNewWorkspaceMode] = React.useState("real");
  const [newWorkspaceChannels, setNewWorkspaceChannels] = React.useState(["Shopify"]);
  const [workspaceCreating, setWorkspaceCreating] = React.useState(false);
  const [deletingWorkspaceId, setDeletingWorkspaceId] = React.useState(null);

  // Stripe SaaS Billing state
  const [billingStatus, setBillingStatus] = React.useState(null);
  const [billingLoading, setBillingLoading] = React.useState(true);
  const [plansList, setPlansList] = React.useState([]);
  const [showPlanModal, setShowPlanModal] = React.useState(false);
  const [selectedInterval, setSelectedInterval] = React.useState("month");
  const [checkoutLoading, setCheckoutLoading] = React.useState(null);
  const [portalLoading, setPortalLoading] = React.useState(false);

  // Stripe Merchant Store Connector state
  const [stripeStatus, setStripeStatus] = React.useState(null);
  const [stripeLoading, setStripeLoading] = React.useState(true);
  const [showStripeInput, setShowStripeInput] = React.useState(false);
  const [stripeApiKey, setStripeApiKey] = React.useState("");
  const [stripeConnecting, setStripeConnecting] = React.useState(false);
  const [stripeSyncing, setStripeSyncing] = React.useState(false);
  const [stripeDisconnecting, setStripeDisconnecting] = React.useState(false);

  const fetchBillingStatus = React.useCallback(async () => {
    try {
      setBillingLoading(true);
      const { data } = await api.get("/billing/status");
      setBillingStatus(data);
    } catch {
      setBillingStatus(null);
    } finally {
      setBillingLoading(false);
    }
  }, []);

  const fetchPlans = React.useCallback(async () => {
    try {
      const { data } = await api.get("/billing/plans");
      setPlansList(data.plans || []);
    } catch {
      setPlansList([]);
    }
  }, []);

  const handleInitiateCheckout = async (planId, interval) => {
    if (billingStatus?.configured === false) {
      toast.error("Stripe billing is not configured in this environment (STRIPE_SECRET_KEY missing).");
      return;
    }
    setCheckoutLoading(planId);
    try {
      const { data } = await api.post("/billing/create-checkout-session", {
        plan_id: planId,
        interval: interval || "month",
      });
      if (data?.checkout_url) {
        if (data.mode === "sandbox") {
          toast.success("Sandbox Mode: Subscription tier activated instantly!");
          setShowPlanModal(false);
          await fetchBillingStatus();
          await qc.invalidateQueries();
        } else {
          toast.info("Redirecting to Stripe Checkout...");
          window.location.assign(data.checkout_url);
        }
      }
    } catch (err) {
      toast.error(formatApiErrorDetail(err?.response?.data?.detail) || "Failed to initiate Stripe Checkout.");
    } finally {
      setCheckoutLoading(null);
    }
  };

  const handleOpenCustomerPortal = async () => {
    if (billingStatus?.configured === false) {
      toast.info("Stripe Customer Portal is unavailable because billing is not configured in this environment.");
      return;
    }
    setPortalLoading(true);
    try {
      const { data } = await api.post("/billing/customer-portal");
      if (data?.portal_url) {
        if (data.mode === "sandbox") {
          toast.info("Sandbox Mode: Billing portal simulated. You can change plans via 'Upgrade / Change Plan'.");
        } else {
          window.location.assign(data.portal_url);
        }
      }
    } catch (err) {
      toast.error(formatApiErrorDetail(err?.response?.data?.detail) || "Stripe Customer Portal is unavailable.");
    } finally {
      setPortalLoading(false);
    }
  };

  const fetchStripeStatus = React.useCallback(async () => {
    try {
      setStripeLoading(true);
      const { data } = await api.get("/integrations/stripe/status");
      setStripeStatus(data);
    } catch {
      setStripeStatus({ connected: false });
    } finally {
      setStripeLoading(false);
    }
  }, []);

  const handleStripeConnect = async (mode = "sandbox") => {
    setStripeConnecting(true);
    try {
      const { data } = await api.post("/integrations/stripe/connect", {
        api_key: stripeApiKey.trim() || undefined,
        mode: mode,
      });
      toast.success(data?.message || "Stripe merchant account connected!");
      setShowStripeInput(false);
      setStripeApiKey("");
      await fetchStripeStatus();
      await qc.invalidateQueries({ queryKey: ["profit"] });
      await qc.invalidateQueries({ queryKey: ["overview"] });
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to connect Stripe merchant account.");
    } finally {
      setStripeConnecting(false);
    }
  };

  const handleStripeSync = async () => {
    setStripeSyncing(true);
    try {
      const { data } = await api.post("/integrations/stripe/sync", { days: 30 });
      toast.success(data?.message || "Stripe fees synchronized into True Profit!");
      await fetchStripeStatus();
      await qc.invalidateQueries({ queryKey: ["profit"] });
      await qc.invalidateQueries({ queryKey: ["overview"] });
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to sync Stripe fees.");
      await fetchStripeStatus();
    } finally {
      setStripeSyncing(false);
    }
  };

  const handleStripeDisconnect = async () => {
    if (!window.confirm("Are you sure you want to disconnect Stripe merchant integration?")) return;
    setStripeDisconnecting(true);
    try {
      await api.post("/integrations/stripe/disconnect");
      toast.success("Stripe merchant integration disconnected.");
      setShowStripeInput(false);
      setStripeApiKey("");
      await fetchStripeStatus();
      await qc.invalidateQueries({ queryKey: ["profit"] });
      await qc.invalidateQueries({ queryKey: ["overview"] });
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to disconnect Stripe.");
    } finally {
      setStripeDisconnecting(false);
    }
  };

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
    fetchBillingStatus();
    fetchPlans();
    fetchStripeStatus();

    // Check for OAuth or billing callback redirect parameters in query string
    const params = new URLSearchParams(window.location.search);
    let shouldClear = false;

    if (params.get("billing") === "success" || params.get("billing") === "sandbox_activated") {
      const p = params.get("plan") || "subscription";
      toast.success(`Successfully activated ${p.toUpperCase()} tier!`);
      fetchBillingStatus();
      shouldClear = true;
    } else if (params.get("billing") === "canceled") {
      toast.info("Checkout was canceled. No charges were made.");
      shouldClear = true;
    }

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
    fetchBillingStatus,
    fetchPlans,
    fetchStripeStatus,
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

  const handleCreateCustomWorkspace = async (e) => {
    e.preventDefault();
    if (!newWorkspaceName.trim()) {
      toast.error("Please enter a workspace name.");
      return;
    }
    setWorkspaceCreating(true);
    try {
      const { data } = await api.post("/workspaces", {
        name: newWorkspaceName.trim(),
        business_type: newWorkspaceType,
        currency: newWorkspaceCurrency,
        mode: newWorkspaceMode,
        channels: newWorkspaceChannels,
      });
      toast.success(`Workspace "${data.name}" created successfully!`);
      setShowCreateWorkspaceModal(false);
      setNewWorkspaceName("");
      await qc.invalidateQueries();
      navigate("/app/overview");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to create workspace.");
    } finally {
      setWorkspaceCreating(false);
    }
  };

  const handleDeleteWorkspace = async (wsId, wsName) => {
    if (workspaces.length <= 1) {
      toast.error("Cannot delete your only workspace. Please create another workspace first.");
      return;
    }
    if (!window.confirm(`Are you sure you want to permanently delete "${wsName}"?\nAll associated data and connections will be removed.`)) {
      return;
    }
    setDeletingWorkspaceId(wsId);
    try {
      const { data } = await api.delete(`/workspaces/${wsId}`);
      toast.success(data?.message || `Workspace "${wsName}" deleted.`);
      await qc.invalidateQueries();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to delete workspace.");
    } finally {
      setDeletingWorkspaceId(null);
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
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <SectionHeader title="Available Workspaces" subtitle="Manage your production brands, client tenants, or sandbox environments" />
          <div className="flex items-center gap-2 self-start sm:self-auto">
            <Button
              onClick={() => setShowCreateWorkspaceModal(true)}
              className="bg-[#00E599] text-xs font-bold text-[#040706] hover:bg-[#00c984] rounded-xl px-3.5"
              data-testid="create-workspace-btn"
            >
              <Plus size={14} className="mr-1" /> New Workspace
            </Button>
            <Button
              onClick={createDemo}
              disabled={creating}
              variant="outline"
              className="border-[#16221B] bg-[#0B110E] text-xs font-semibold text-[#CBD5E1] hover:bg-[#121C16] hover:border-[#1F3327] rounded-xl"
              data-testid="create-demo-btn"
            >
              {creating ? <Loader2 className="animate-spin" size={14} /> : <><Sparkles size={13} className="mr-1.5 text-[#00E599]" /> Quick Demo</>}
            </Button>
          </div>
        </div>
        <div className="mt-4 space-y-2.5">
          {workspaces.map((w) => (
            <div
              key={w.workspace_id}
              className="flex items-center justify-between rounded-xl border border-[#16221B] bg-[#0B110E] px-4 py-3 transition-all hover:border-[#1F3327]"
            >
              <div className="flex items-center gap-3">
                <span className={`flex h-8 w-8 items-center justify-center rounded-lg border text-xs font-bold ${
                  w.is_demo
                    ? "border-sky-500/30 bg-sky-500/10 text-sky-400"
                    : "border-[#00E599]/30 bg-[#00E599]/15 text-[#00E599]"
                }`}>
                  {w.name.slice(0, 1).toUpperCase()}
                </span>
                <div>
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-semibold text-[#F8FAFC]">{w.name}</p>
                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold border ${
                      w.is_demo
                        ? "border-sky-500/30 bg-sky-500/10 text-sky-400"
                        : "border-emerald-500/30 bg-emerald-500/10 text-[#00E599]"
                    }`}>
                      {w.is_demo ? "Demo Sandbox" : "Live Production"}
                    </span>
                  </div>
                  <p className="text-xs text-[#64748B] mt-0.5">
                    {w.business_type || "DTC Brand"} · Currency: {w.currency || "USD"}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
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

                {/* Delete Workspace Button */}
                <Button
                  size="icon"
                  variant="ghost"
                  onClick={() => handleDeleteWorkspace(w.workspace_id, w.name)}
                  disabled={workspaces.length <= 1 || deletingWorkspaceId === w.workspace_id}
                  className="h-8 w-8 text-[#64748B] hover:text-rose-400 hover:bg-rose-950/30 rounded-lg disabled:opacity-30"
                  title={workspaces.length <= 1 ? "Cannot delete your only workspace" : "Delete workspace"}
                  data-testid={`delete-workspace-${w.workspace_id}`}
                >
                  {deletingWorkspaceId === w.workspace_id ? <Loader2 className="animate-spin" size={13} /> : <Trash2 size={14} />}
                </Button>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* SaaS Subscription & Billing Card */}
      <Card className="p-6 border-[#16221B] bg-[#070C0A]">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <SectionHeader
            title="SaaS Subscription & Billing"
            subtitle="Manage your AHONIX operating system tier, customer invoices, and platform access"
            icon={CreditCard}
          />
          <div className="flex items-center gap-2 self-start sm:self-auto">
            <Button
              size="sm"
              variant="outline"
              onClick={handleOpenCustomerPortal}
              disabled={portalLoading}
              className="border-[#16221B] bg-[#0B110E] text-xs font-semibold text-[#F8FAFC] hover:bg-[#121C16] hover:border-[#1F3327] rounded-xl"
              data-testid="billing-portal-btn"
            >
              {portalLoading ? <Loader2 size={13} className="animate-spin mr-1.5" /> : <ExternalLink size={13} className="mr-1.5 text-[#00E599]" />}
              Customer Portal
            </Button>
            <Button
              size="sm"
              onClick={() => setShowPlanModal(true)}
              className="bg-[#00E599] text-xs font-bold text-[#040706] hover:bg-[#00c984] rounded-xl px-3.5"
              data-testid="upgrade-plan-btn"
            >
              <Sparkles size={13} className="mr-1.5" />
              Upgrade / Change Plan
            </Button>
          </div>
        </div>

        <div className="mt-5 grid grid-cols-1 sm:grid-cols-4 gap-4">
          <div className="rounded-xl border border-[#16221B] bg-[#0B110E] p-4">
            <p className="text-[11px] font-medium text-[#64748B] uppercase tracking-wider">Active Plan</p>
            <div className="mt-1 flex items-center gap-2">
              <p className="text-base font-bold text-[#F8FAFC] capitalize">
                {billingStatus?.plan_name || (billingStatus?.is_demo ? "Demo Sandbox Tier" : "Free Tier")}
              </p>
              {billingStatus?.has_active_subscription && (
                <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-bold text-[#00E599] border border-emerald-500/20">
                  {billingStatus?.interval === "year" ? "Annual" : "Monthly"}
                </span>
              )}
            </div>
          </div>

          <div className="rounded-xl border border-[#16221B] bg-[#0B110E] p-4">
            <p className="text-[11px] font-medium text-[#64748B] uppercase tracking-wider">Subscription Status</p>
            <div className="mt-1 flex items-center gap-2">
              <span className={`h-2 w-2 rounded-full ${billingStatus?.has_active_subscription ? "bg-[#00E599] animate-pulse" : "bg-slate-500"}`} />
              <p className="text-sm font-semibold text-[#F8FAFC] capitalize">
                {billingStatus?.has_active_subscription
                  ? (billingStatus?.status === "trialing"
                      ? `Trial (${billingStatus.trial_days_remaining}d left)`
                      : billingStatus?.status || "Active")
                  : (billingStatus?.is_demo ? "Demo Sandbox" : "Free Tier / Unconfigured")}
              </p>
            </div>
          </div>

          <div className="rounded-xl border border-[#16221B] bg-[#0B110E] p-4">
            <p className="text-[11px] font-medium text-[#64748B] uppercase tracking-wider">Renewal / End Date</p>
            <p className="mt-1 text-sm font-semibold text-[#CBD5E1]">
              {billingStatus?.current_period_end
                ? new Date(billingStatus.current_period_end).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })
                : "No active renewal"}
            </p>
          </div>

          <div className="rounded-xl border border-[#16221B] bg-[#0B110E] p-4">
            <p className="text-[11px] font-medium text-[#64748B] uppercase tracking-wider">Payment Gateway</p>
            <p className="mt-1 text-xs font-semibold text-[#94A3B8]">
              {billingStatus?.configured
                ? (billingStatus?.is_sandbox ? "Stripe Sandbox Mode" : "Stripe Live Production")
                : "Stripe Not Configured"}
            </p>
          </div>
        </div>

        {billingStatus?.features && (
          <div className="mt-4 pt-4 border-t border-[#16221B] flex flex-wrap items-center gap-2.5">
            <span className="text-xs text-[#64748B] font-medium mr-1">Plan features:</span>
            {billingStatus.features.slice(0, 4).map((f, i) => (
              <span key={i} className="inline-flex items-center gap-1.5 rounded-lg border border-[#16221B] bg-[#0B110E] px-2.5 py-1 text-xs text-[#CBD5E1]">
                <Check size={12} className="text-[#00E599]" /> {f}
              </span>
            ))}
          </div>
        )}
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

        {/* Stripe Merchant Store Connector Card */}
        <div className="mt-4 rounded-xl border border-[#16221B] bg-[#0B110E] p-4 transition-all hover:border-[#1F3327]">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3.5">
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 font-bold text-sm">
                <CreditCard size={18} />
              </span>
              <div>
                <div className="flex items-center gap-2">
                  <p className="text-sm font-semibold text-[#F8FAFC]">Stripe Merchant Payments</p>
                  {stripeLoading ? (
                    <Loader2 size={13} className="animate-spin text-[#64748B]" />
                  ) : stripeStatus?.connected ? (
                    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-[11px] font-medium text-[#00E599] border border-emerald-500/20" data-testid="stripe-connected-badge">
                      <CheckCircle2 size={11} /> Connected ({stripeStatus.mode === "live" ? "Live" : "Sandbox"})
                    </span>
                  ) : (
                    <span className="rounded-full bg-[#121C16] border border-[#16221B] px-2 py-0.5 text-[11px] text-[#64748B]">
                      Payment Gateway
                    </span>
                  )}
                </div>
                <p className="text-xs text-[#64748B] mt-0.5">
                  {stripeStatus?.connected
                    ? `Account: ${stripeStatus.account_id} · Ingesting card processing fees into True Profit waterfall`
                    : "Connect Stripe to automatically deduct card fees (2.9% + $0.30/txn) from gross revenue in True Profit"}
                </p>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex items-center gap-2">
              {stripeStatus?.connected ? (
                <>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleStripeSync}
                    disabled={stripeSyncing}
                    className="border-[#16221B] bg-[#121C16] text-xs font-semibold text-[#F8FAFC] hover:bg-[#16221B] rounded-lg"
                    data-testid="stripe-sync-btn"
                  >
                    <RefreshCw size={13} className={`mr-1.5 ${stripeSyncing ? "animate-spin text-[#00E599]" : ""}`} />
                    {stripeSyncing ? "Syncing..." : "Sync Fees"}
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={handleStripeDisconnect}
                    disabled={stripeDisconnecting}
                    className="text-xs text-rose-400 hover:bg-rose-950/20 hover:text-rose-300 rounded-lg"
                    data-testid="stripe-disconnect-btn"
                  >
                    {stripeDisconnecting ? <Loader2 size={13} className="animate-spin" /> : <><Unlink size={13} className="mr-1" /> Disconnect</>}
                  </Button>
                </>
              ) : (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setShowStripeInput(!showStripeInput)}
                  className="border-indigo-500/30 bg-indigo-500/10 text-xs font-semibold text-indigo-400 hover:bg-indigo-500/20 rounded-lg"
                  data-testid="connect-stripe-btn"
                >
                  {showStripeInput ? "Cancel" : "Connect Stripe"}
                </Button>
              )}
            </div>
          </div>

          {/* Connect Input Form */}
          {!stripeStatus?.connected && showStripeInput && (
            <div className="mt-4 rounded-xl border border-[#16221B] bg-[#070C0A] p-4" data-testid="stripe-connect-form">
              <p className="text-xs font-medium text-[#F8FAFC] mb-2">Connect Stripe Account:</p>
              <div className="space-y-3">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                  <input
                    type="password"
                    value={stripeApiKey}
                    onChange={(e) => setStripeApiKey(e.target.value)}
                    placeholder="rk_live_... or sk_test_... (or leave blank for Sandbox)"
                    className="w-full rounded-xl border border-[#16221B] bg-[#0B110E] px-3.5 py-2 text-xs text-[#F8FAFC] placeholder-[#64748B] focus:border-[#00E599] focus:outline-none font-mono"
                    data-testid="stripe-api-key-input"
                  />
                  <Button
                    size="sm"
                    onClick={() => handleStripeConnect(stripeApiKey.trim() ? "live" : "sandbox")}
                    disabled={stripeConnecting}
                    className="bg-[#00E599] text-xs font-bold text-[#040706] hover:bg-[#00c984] rounded-xl px-4 py-2 shrink-0"
                    data-testid="stripe-submit-connect-btn"
                  >
                    {stripeConnecting ? <Loader2 size={13} className="animate-spin mr-1.5" /> : <ExternalLink size={13} className="mr-1.5" />}
                    {stripeApiKey.trim() ? "Connect Live API Key" : "Connect Demo Sandbox"}
                  </Button>
                </div>
                <p className="text-[11px] text-[#64748B]">
                  Tokens are encrypted with AES-256-GCM. We only require read-only balance permissions (<code className="text-indigo-400">rak_balance_read</code>) to compute transaction processing deductions.
                </p>
              </div>
            </div>
          )}

          {/* Sync Status Subpanel */}
          {stripeStatus?.connected && (
            <div className="mt-3.5 border-t border-[#16221B] pt-3 text-xs text-[#64748B]" data-testid="stripe-sync-status-panel">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-3">
                  <span>
                    Ingestion Status:{" "}
                    <span className={`font-semibold ${
                      stripeStatus.sync_status === "success"
                        ? "text-[#00E599]"
                        : stripeStatus.sync_status === "failed"
                        ? "text-rose-400"
                        : stripeStatus.sync_status === "syncing"
                        ? "text-cyan-400"
                        : "text-[#94A3B8]"
                    }`}>
                      {stripeStatus.sync_status?.toUpperCase() || "IDLE"}
                    </span>
                  </span>
                  <span>·</span>
                  <span>
                    Last Synced:{" "}
                    <span className="text-[#CBD5E1]">
                      {stripeStatus.last_synced_at
                        ? new Date(stripeStatus.last_synced_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
                        : "Never"}
                    </span>
                  </span>
                </div>

                <div className="flex items-center gap-2 text-[11px]">
                  <span className="rounded-lg bg-[#070C0A] px-2.5 py-1 text-[#94A3B8] border border-[#16221B]">
                    Fee Rate: <strong className="text-[#F8FAFC]">{stripeStatus.fee_rate_pct || 2.9}% + $0.30</strong>
                  </span>
                  {stripeStatus.total_fees_synced > 0 && (
                    <span className="rounded-lg bg-emerald-500/10 px-2.5 py-1 text-[#00E599] border border-emerald-500/20 font-semibold">
                      ${Number(stripeStatus.total_fees_synced).toLocaleString(undefined, { minimumFractionDigits: 2 })} Fees Deducted
                    </span>
                  )}
                </div>
              </div>

              {stripeStatus.sync_error && (
                <div className="mt-2.5 flex items-center gap-2 rounded-lg bg-rose-950/20 px-3 py-2 text-xs text-rose-300 border border-rose-900/30">
                  <AlertCircle size={14} className="shrink-0 text-rose-400" />
                  <span>Sync Error: {stripeStatus.sync_error}</span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Other integrations (architecture-ready) */}
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {INTEGRATIONS.filter((it) => !["Shopify", "Meta Ads", "Google Ads", "Stripe"].includes(it.name)).map((it) => (
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

      {/* Plan Selector Modal */}
      {showPlanModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-fade-in"
          onClick={() => setShowPlanModal(false)}
        >
          <div
            className="relative w-full max-w-4xl max-h-[90vh] overflow-y-auto rounded-2xl border border-[#16221B] bg-[#070C0A] p-6 sm:p-8 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              onClick={() => setShowPlanModal(false)}
              className="absolute right-5 top-5 rounded-lg border border-[#16221B] bg-[#0B110E] p-1.5 text-[#94A3B8] hover:text-white"
              aria-label="Close modal"
            >
              <X size={16} />
            </button>

            <div className="text-center max-w-lg mx-auto">
              <div className="inline-flex items-center gap-1.5 rounded-full border border-[#16221B] bg-[#0B1410] px-3 py-1 text-xs font-semibold text-[#00E599] mb-3">
                <Sparkles size={13} />
                <span>AHONIX OPERATING SYSTEM TIERS</span>
              </div>
              <h3 className="font-display text-2xl font-bold text-[#F8FAFC]">
                Select the Right Plan for Your Scale
              </h3>
              <p className="mt-1 text-xs text-[#94A3B8]">
                All plans include 14 days free trial. Cancel or change tiers at any time via Stripe Portal.
              </p>

              {/* Monthly / Annual Toggle */}
              <div className="mt-5 inline-flex items-center rounded-full border border-[#16221B] bg-[#0B110E] p-1">
                <button
                  onClick={() => setSelectedInterval("month")}
                  className={`rounded-full px-4 py-1.5 text-xs font-semibold transition-all ${
                    selectedInterval === "month"
                      ? "bg-[#16221B] text-[#F8FAFC]"
                      : "text-[#94A3B8] hover:text-[#F8FAFC]"
                  }`}
                >
                  Monthly
                </button>
                <button
                  onClick={() => setSelectedInterval("year")}
                  className={`flex items-center gap-1.5 rounded-full px-4 py-1.5 text-xs font-semibold transition-all ${
                    selectedInterval === "year"
                      ? "bg-[#00E599] text-[#040706]"
                      : "text-[#94A3B8] hover:text-[#F8FAFC]"
                  }`}
                >
                  <span>Annual</span>
                  <span className="rounded-full bg-black/20 px-1.5 py-0.5 text-[10px] font-bold">SAVE 20%</span>
                </button>
              </div>
            </div>

            {/* Plans Grid */}
            <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-5">
              {plansList.map((plan) => {
                const isCurrent = billingStatus?.plan_id === plan.id;
                const isPopular = plan.popular;
                const price = selectedInterval === "year" ? plan.annual_price : plan.monthly_price;

                return (
                  <div
                    key={plan.id}
                    className={`relative flex flex-col justify-between rounded-2xl border p-5 sm:p-6 transition-all ${
                      isPopular
                        ? "border-[#00E599] bg-[#08130E] shadow-xl shadow-[#00E599]/10"
                        : "border-[#16221B] bg-[#0B110E] hover:border-[#1F3327]"
                    }`}
                  >
                    {isPopular && (
                      <div className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-[#00E599] px-3 py-0.5 text-[10px] font-extrabold tracking-wider text-[#040706] uppercase">
                        Most Popular
                      </div>
                    )}

                    <div>
                      <div className="flex items-center justify-between">
                        <h4 className="font-display text-lg font-bold text-[#F8FAFC]">{plan.name}</h4>
                        <span className="font-mono text-[11px] text-[#64748B]">{plan.stores_limit === 999 ? "Unlimited Stores" : `${plan.stores_limit} Store`}</span>
                      </div>
                      <p className="mt-1 text-xs text-[#94A3B8] min-h-[32px]">{plan.tagline}</p>

                      <div className="mt-4 flex items-baseline gap-1">
                        <span className="font-display text-3xl font-extrabold text-[#F8FAFC]">
                          ${price}
                        </span>
                        <span className="text-xs text-[#64748B]">/ month</span>
                      </div>
                      {selectedInterval === "year" && (
                        <p className="text-[11px] text-[#00E599] mt-0.5">Billed annually (${price * 12}/yr)</p>
                      )}

                      <div className="mt-5 space-y-2 border-t border-[#16221B] pt-4">
                        {plan.features.map((f, idx) => (
                          <div key={idx} className="flex items-center gap-2 text-xs text-[#CBD5E1]">
                            <Check size={13} className="text-[#00E599] shrink-0" />
                            <span>{f}</span>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="mt-6 pt-4 border-t border-[#16221B]">
                      {isCurrent ? (
                        <Button
                          disabled
                          variant="outline"
                          className="w-full border-emerald-500/30 bg-emerald-500/10 text-xs font-bold text-[#00E599] rounded-xl"
                        >
                          <Check size={13} className="mr-1.5" /> Current Plan
                        </Button>
                      ) : (
                        <Button
                          onClick={() => handleInitiateCheckout(plan.id, selectedInterval)}
                          disabled={checkoutLoading === plan.id}
                          className={`w-full text-xs font-bold rounded-xl py-2.5 ${
                            isPopular
                              ? "bg-[#00E599] text-[#040706] hover:bg-[#00c984] shadow-md shadow-[#00E599]/20"
                              : "border border-[#16221B] bg-[#070C0A] text-[#F8FAFC] hover:bg-[#121C16] hover:border-[#1F3327]"
                          }`}
                          data-testid={`select-plan-${plan.id}`}
                        >
                          {checkoutLoading === plan.id ? (
                            <Loader2 size={13} className="animate-spin mr-1.5" />
                          ) : (
                            <Sparkles size={13} className="mr-1.5" />
                          )}
                          {checkoutLoading === plan.id ? "Connecting to Stripe..." : `Upgrade to ${plan.name}`}
                        </Button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
      {/* Create Workspace Modal */}
      {showCreateWorkspaceModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-fade-in"
          onClick={() => setShowCreateWorkspaceModal(false)}
        >
          <div
            className="relative w-full max-w-lg rounded-2xl border border-[#16221B] bg-[#070C0A] p-6 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              onClick={() => setShowCreateWorkspaceModal(false)}
              className="absolute right-5 top-5 rounded-lg border border-[#16221B] bg-[#0B110E] p-1.5 text-[#94A3B8] hover:text-white"
              aria-label="Close modal"
            >
              <X size={16} />
            </button>

            <div className="flex items-center gap-3 mb-5">
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#00E599]/15 text-[#00E599] border border-[#00E599]/30">
                <Building2 size={18} />
              </span>
              <div>
                <h3 className="font-display text-lg font-bold text-[#F8FAFC]">
                  Create New Workspace
                </h3>
                <p className="text-xs text-[#94A3B8]">
                  Deploy an isolated tenant for your brand or store.
                </p>
              </div>
            </div>

            <form onSubmit={handleCreateCustomWorkspace} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-[#94A3B8] mb-1.5">
                  Store / Workspace Name *
                </label>
                <input
                  type="text"
                  required
                  value={newWorkspaceName}
                  onChange={(e) => setNewWorkspaceName(e.target.value)}
                  placeholder="e.g. Apex Athletics, Nomad Goods"
                  className="w-full rounded-xl border border-[#16221B] bg-[#0B110E] px-3.5 py-2.5 text-xs text-[#F8FAFC] placeholder-[#64748B] focus:border-[#00E599] focus:outline-none"
                  data-testid="workspace-name-input"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-[#94A3B8] mb-1.5">
                    Operating Model
                  </label>
                  <select
                    value={newWorkspaceType}
                    onChange={(e) => setNewWorkspaceType(e.target.value)}
                    className="w-full rounded-xl border border-[#16221B] bg-[#0B110E] px-3 py-2.5 text-xs text-[#F8FAFC] focus:border-[#00E599] focus:outline-none"
                  >
                    <option value="DTC Brand">DTC Brand</option>
                    <option value="Marketplace Seller">Marketplace Seller</option>
                    <option value="Omnichannel Brand">Omnichannel Brand</option>
                    <option value="Agency / Multi-Store">Agency / Multi-Store</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-[#94A3B8] mb-1.5">
                    Functional Currency
                  </label>
                  <select
                    value={newWorkspaceCurrency}
                    onChange={(e) => setNewWorkspaceCurrency(e.target.value)}
                    className="w-full rounded-xl border border-[#16221B] bg-[#0B110E] px-3 py-2.5 text-xs text-[#F8FAFC] focus:border-[#00E599] focus:outline-none"
                  >
                    <option value="USD">USD ($)</option>
                    <option value="EUR">EUR (€)</option>
                    <option value="GBP">GBP (£)</option>
                    <option value="CAD">CAD ($)</option>
                    <option value="AUD">AUD ($)</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#94A3B8] mb-1.5">
                  Telemetry Mode
                </label>
                <div className="grid grid-cols-2 gap-2.5">
                  <button
                    type="button"
                    onClick={() => setNewWorkspaceMode("real")}
                    className={`rounded-xl border p-3 text-left transition-all ${
                      newWorkspaceMode === "real"
                        ? "border-[#00E599] bg-emerald-500/10 text-[#F8FAFC]"
                        : "border-[#16221B] bg-[#0B110E] text-[#94A3B8] hover:border-[#1F3327]"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-[#F8FAFC]">Live Production</span>
                      {newWorkspaceMode === "real" && <Check size={14} className="text-[#00E599]" />}
                    </div>
                    <p className="text-[11px] text-[#64748B] mt-1">
                      Ready to connect real Shopify, Stripe, or Ads data.
                    </p>
                  </button>

                  <button
                    type="button"
                    onClick={() => setNewWorkspaceMode("demo")}
                    className={`rounded-xl border p-3 text-left transition-all ${
                      newWorkspaceMode === "demo"
                        ? "border-sky-400 bg-sky-500/10 text-[#F8FAFC]"
                        : "border-[#16221B] bg-[#0B110E] text-[#94A3B8] hover:border-[#1F3327]"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-[#F8FAFC]">Demo Sandbox</span>
                      {newWorkspaceMode === "demo" && <Check size={14} className="text-sky-400" />}
                    </div>
                    <p className="text-[11px] text-[#64748B] mt-1">
                      Pre-populated with DTC order & spend benchmarks.
                    </p>
                  </button>
                </div>
              </div>

              <div className="mt-6 flex items-center justify-end gap-3 pt-3 border-t border-[#16221B]">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setShowCreateWorkspaceModal(false)}
                  className="border-[#16221B] bg-[#0B110E] text-xs text-[#94A3B8] hover:text-white rounded-xl"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={workspaceCreating || !newWorkspaceName.trim()}
                  className="bg-[#00E599] text-xs font-bold text-[#040706] hover:bg-[#00c984] rounded-xl px-4"
                  data-testid="submit-create-workspace"
                >
                  {workspaceCreating ? <Loader2 size={14} className="animate-spin mr-1.5" /> : <Plus size={14} className="mr-1.5" />}
                  {workspaceCreating ? "Creating..." : "Create Workspace"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
