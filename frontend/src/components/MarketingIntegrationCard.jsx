import React, { useState } from "react";
import {
  RefreshCw,
  Unlink,
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  ExternalLink,
  Loader2,
  Lock,
  ChevronDown,
  ChevronUp,
  Check,
  Building,
} from "lucide-react";
import { Button } from "@/components/ui/button";

// Meta and Google Ads Brand Icons
export function MetaIcon({ className = "w-5 h-5" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path
        fill="#0081FB"
        d="M16.96 4C14.77 4 13.06 5.17 12 6.64 10.94 5.17 9.23 4 7.04 4 3.15 4 0 7.15 0 11.04c0 4.88 4.79 8.96 12 12.96 7.21-4 12-8.08 12-12.96C24 7.15 20.85 4 16.96 4zm-4.96 11.23C8.42 12.91 4.5 10.5 4.5 7.85c0-1.85 1.5-3.35 3.35-3.35 1.48 0 2.87 1.07 3.32 2.5h1.66c.45-1.43 1.84-2.5 3.32-2.5 1.85 0 3.35 1.5 3.35 3.35 0 2.65-3.92 5.06-7.5 7.38z"
      />
    </svg>
  );
}

export function GoogleAdsIcon({ className = "w-5 h-5" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      <path
        d="M3.5 16.5L9.5 6L14 13.5H3.5V16.5Z"
        fill="#FBBC04"
      />
      <circle cx="17.5" cy="14.5" r="4.5" fill="#4285F4" />
      <path
        d="M9.5 6L15.5 16.5H5.5L9.5 6Z"
        fill="#34A853"
      />
    </svg>
  );
}

export function MarketingIntegrationCard({
  platform, // "meta" | "google_ads"
  title,
  description,
  workspace,
  statusData,
  statusLoading,
  onConnect,
  onDisconnect,
  onSync,
  onSelectAccount,
  accountsData,
  accountsLoading,
  onFetchAccounts,
}) {
  const [connecting, setConnecting] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [showAccounts, setShowAccounts] = useState(false);
  const [selectedAccountId, setSelectedAccountId] = useState(null);
  const [savingAccount, setSavingAccount] = useState(false);

  const isDemo = workspace?.is_demo;
  const isConnected = Boolean(statusData?.connected);
  const isReauthRequired = statusData?.status === "reauth_required";
  const isCurrencyMismatch = Boolean(statusData?.currency_mismatch);
  const syncStatus = statusData?.sync_status || "idle";
  const isSyncingActive = syncStatus === "syncing" || syncing;
  const syncError = statusData?.sync_error;
  const lastSync = statusData?.last_sync_at;

  const storeCurrency = (workspace?.currency || "USD").toUpperCase();

  const handleConnectClick = async () => {
    if (isDemo || connecting) return;
    setConnecting(true);
    try {
      await onConnect();
    } finally {
      setConnecting(false);
    }
  };

  const handleSyncClick = async () => {
    if (isDemo || syncing || isSyncingActive) return;
    setSyncing(true);
    try {
      await onSync();
    } finally {
      setSyncing(false);
    }
  };

  const handleDisconnectClick = async () => {
    if (isDemo || disconnecting) return;
    setDisconnecting(true);
    try {
      await onDisconnect();
      setShowAccounts(false);
    } finally {
      setDisconnecting(false);
    }
  };

  const handleToggleAccounts = () => {
    if (!showAccounts && onFetchAccounts) {
      onFetchAccounts();
    }
    setShowAccounts(!showAccounts);
  };

  const handleAccountSelect = async (account) => {
    if (isDemo || savingAccount) return;
    setSavingAccount(true);
    try {
      await onSelectAccount(account);
      setShowAccounts(false);
    } finally {
      setSavingAccount(false);
    }
  };

  const formatDateTime = (isoString) => {
    if (!isoString) return "Never";
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return String(isoString);
    }
  };

  return (
    <div
      className={`rounded-lg border bg-[#0F111A] p-5 transition-all ${
        isCurrencyMismatch
          ? "border-amber-500/40"
          : isReauthRequired
          ? "border-amber-500/50"
          : isConnected
          ? "border-[#1E2235] hover:border-[#2D334B]"
          : "border-[#1E2235]/80 opacity-90"
      }`}
      data-testid={`marketing-card-${platform}`}
    >
      {/* Header Row */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3.5">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-[#2D334B] bg-[#161926]">
            {platform === "meta" ? (
              <MetaIcon className="h-5 w-5" />
            ) : (
              <GoogleAdsIcon className="h-5 w-5" />
            )}
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-sm font-semibold text-[#F8FAFC]">{title}</h3>

              {/* Status Badges */}
              {statusLoading ? (
                <Loader2 size={13} className="animate-spin text-[#64748B]" />
              ) : isDemo ? (
                <span className="inline-flex items-center gap-1 rounded-full border border-amber-500/20 bg-amber-500/10 px-2.5 py-0.5 text-[11px] font-medium text-amber-300">
                  <Lock size={10} /> Demo Locked
                </span>
              ) : isReauthRequired ? (
                <span
                  className="inline-flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-0.5 text-[11px] font-medium text-amber-300"
                  data-testid={`${platform}-reauth-badge`}
                >
                  <AlertTriangle size={11} /> Re-auth Required
                </span>
              ) : isConnected ? (
                <span
                  className="inline-flex items-center gap-1 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-0.5 text-[11px] font-medium text-emerald-400"
                  data-testid={`${platform}-connected-badge`}
                >
                  <CheckCircle2 size={11} /> Connected
                </span>
              ) : (
                <span className="rounded-full border border-[#1E2235] bg-[#161926] px-2.5 py-0.5 text-[11px] font-medium text-[#94A3B8]">
                  Disconnected
                </span>
              )}

              {/* Currency Mismatch Tag */}
              {isCurrencyMismatch && (
                <span
                  className="inline-flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium text-amber-300"
                  data-testid={`${platform}-currency-mismatch-badge`}
                >
                  <AlertCircle size={10} /> Currency Mismatch
                </span>
              )}

              {/* Google Manager Account Tag */}
              {platform === "google_ads" && statusData?.login_customer_id && (
                <span className="inline-flex items-center gap-1 rounded-full border border-cyan-500/20 bg-cyan-500/10 px-2 py-0.5 text-[10px] font-medium text-cyan-300">
                  Manager Account
                </span>
              )}
            </div>

            <p className="mt-1 text-xs text-[#94A3B8] leading-relaxed">
              {isConnected
                ? platform === "meta"
                  ? statusData?.selected_account_name
                    ? `Account: ${statusData.selected_account_name} (${statusData.selected_account_id})`
                    : "Account connected. Select an active ad account to sync campaigns."
                  : statusData?.selected_account_name
                  ? `Customer: ${statusData.selected_account_name} (${statusData.selected_customer_id})`
                  : "Google Ads connected. Select an accessible customer account to sync campaigns."
                : description}
            </p>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-wrap items-center gap-2 shrink-0">
          {isDemo ? (
            <div className="flex items-center gap-1 text-xs text-[#64748B]">
              <Lock size={12} />
              <span>Disabled in Demo</span>
            </div>
          ) : isConnected ? (
            <>
              <Button
                size="sm"
                variant="outline"
                onClick={handleToggleAccounts}
                className="border-[#2D334B] bg-[#161926] text-xs text-[#CBD5E1] hover:bg-[#1E2235]"
                data-testid={`${platform}-select-account-btn`}
              >
                <Building size={12} className="mr-1.5 text-[#94A3B8]" />
                {statusData?.selected_account_id || statusData?.selected_customer_id
                  ? "Change Account"
                  : "Select Account"}
                {showAccounts ? (
                  <ChevronUp size={12} className="ml-1" />
                ) : (
                  <ChevronDown size={12} className="ml-1" />
                )}
              </Button>

              <Button
                size="sm"
                variant="outline"
                onClick={handleSyncClick}
                disabled={isSyncingActive}
                className="border-[#2D334B] bg-[#161926] text-xs text-[#F8FAFC] hover:bg-[#1E2235]"
                data-testid={`${platform}-sync-btn`}
              >
                <RefreshCw
                  size={12}
                  className={`mr-1.5 ${isSyncingActive ? "animate-spin text-cyan-400" : ""}`}
                />
                {isSyncingActive ? "Syncing..." : "Sync Now"}
              </Button>

              <Button
                size="sm"
                variant="ghost"
                onClick={handleDisconnectClick}
                disabled={disconnecting}
                className="text-xs text-rose-400 hover:bg-rose-950/20 hover:text-rose-300"
                data-testid={`${platform}-disconnect-btn`}
              >
                {disconnecting ? (
                  <Loader2 size={12} className="animate-spin mr-1" />
                ) : (
                  <Unlink size={12} className="mr-1" />
                )}
                Disconnect
              </Button>
            </>
          ) : (
            <Button
              size="sm"
              variant="outline"
              onClick={handleConnectClick}
              disabled={connecting}
              className="border-emerald-500/30 bg-emerald-500/10 text-xs font-medium text-emerald-400 hover:bg-emerald-500/20"
              data-testid={`${platform}-connect-btn`}
            >
              {connecting ? (
                <Loader2 size={12} className="animate-spin mr-1.5" />
              ) : (
                <ExternalLink size={12} className="mr-1.5" />
              )}
              {connecting ? "Redirecting..." : `Connect ${title}`}
            </Button>
          )}
        </div>
      </div>

      {/* Demo Workspace Explanation */}
      {isDemo && (
        <div className="mt-3.5 flex items-center gap-2 rounded border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-xs text-amber-300/90">
          <Lock size={13} className="shrink-0 text-amber-400" />
          <span>
            Demo integrations are read-only and locked for Northstar Goods to protect baseline analytics. Switch to a live workspace to connect real ad platforms.
          </span>
        </div>
      )}

      {/* Re-auth Required Banner */}
      {!isDemo && isReauthRequired && (
        <div
          className="mt-3.5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2.5 rounded border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-200"
          data-testid={`${platform}-reauth-banner`}
        >
          <div className="flex items-start gap-2">
            <AlertTriangle size={15} className="shrink-0 mt-0.5 text-amber-400" />
            <div>
              <p className="font-semibold text-amber-100">Authentication Expired or Revoked</p>
              <p className="text-amber-200/80 mt-0.5">
                The OAuth token for {title} is invalid or expired. Re-authenticate to resume syncing campaign insights.
              </p>
            </div>
          </div>
          <Button
            size="sm"
            onClick={handleConnectClick}
            disabled={connecting}
            className="bg-amber-500 text-amber-950 font-semibold text-xs hover:bg-amber-400 shrink-0"
            data-testid={`${platform}-reconnect-btn`}
          >
            {connecting ? <Loader2 size={12} className="animate-spin mr-1.5" /> : <ExternalLink size={12} className="mr-1.5" />}
            Reconnect Now
          </Button>
        </div>
      )}

      {/* Currency Mismatch Warning Box */}
      {!isDemo && isCurrencyMismatch && (
        <div
          className="mt-3.5 flex items-start gap-2.5 rounded border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-200"
          data-testid={`${platform}-currency-mismatch-warning`}
        >
          <AlertCircle size={15} className="shrink-0 mt-0.5 text-amber-400" />
          <div>
            <p className="font-semibold text-amber-100">Currency Mismatch Detected</p>
            <p className="text-amber-200/80 mt-0.5">
              Ad account currency (<strong>{statusData?.account_currency || "Unknown"}</strong>) does not match your store currency (<strong>{storeCurrency}</strong>).
              AHONIX strictly avoids unverified currency conversion. Spend from this account is tracked separately and excluded from True Profit totals.
            </p>
          </div>
        </div>
      )}

      {/* Sync Error Notice */}
      {!isDemo && isConnected && syncError && (
        <div
          className="mt-3 flex items-start gap-2 rounded border border-rose-500/30 bg-rose-500/10 p-2.5 text-xs text-rose-200"
          data-testid={`${platform}-sync-error`}
        >
          <AlertCircle size={14} className="shrink-0 mt-0.5 text-rose-400" />
          <span>Sync Error: {syncError}</span>
        </div>
      )}

      {/* Connected Details Bar */}
      {!isDemo && isConnected && (
        <div className="mt-4 border-t border-[#1E2235] pt-3 text-xs text-[#64748B]">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-3">
              <span>
                Sync Status:{" "}
                <span
                  className={`font-medium ${
                    syncStatus === "success"
                      ? "text-emerald-400"
                      : syncStatus === "failed"
                      ? "text-rose-400"
                      : syncStatus === "syncing"
                      ? "text-cyan-400"
                      : "text-[#94A3B8]"
                  }`}
                >
                  {syncStatus.toUpperCase()}
                </span>
              </span>
              <span>·</span>
              <span>
                Last Successful Sync:{" "}
                <span className="text-[#94A3B8] font-metric">
                  {formatDateTime(lastSync)}
                </span>
              </span>
              {statusData?.account_currency && (
                <>
                  <span>·</span>
                  <span>
                    Currency:{" "}
                    <span className="font-semibold text-[#CBD5E1]">
                      {statusData.account_currency}
                    </span>
                  </span>
                </>
              )}
            </div>

            <div className="text-[11px] text-[#64748B]">
              {platform === "meta"
                ? `Meta Graph API: ${statusData?.api_version || "v21.0"}`
                : "Google Ads API: v18"}
            </div>
          </div>
        </div>
      )}

      {/* Account Selection Panel (Dropdown / Expandable) */}
      {!isDemo && isConnected && showAccounts && (
        <div
          className="mt-4 rounded-lg border border-[#2D334B] bg-[#121420] p-4 text-xs"
          data-testid={`${platform}-accounts-panel`}
        >
          <div className="flex items-center justify-between mb-3">
            <p className="font-semibold text-[#F8FAFC]">
              Select {platform === "meta" ? "Meta Ad Account" : "Google Ads Customer"}
            </p>
            <span className="text-[11px] text-[#64748B]">
              Store currency: <strong>{storeCurrency}</strong>
            </span>
          </div>

          {accountsLoading ? (
            <div className="flex items-center justify-center py-6 text-[#94A3B8]">
              <Loader2 size={16} className="animate-spin mr-2 text-emerald-400" />
              <span>Fetching accessible accounts...</span>
            </div>
          ) : accountsData?.accounts?.length ? (
            <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
              {accountsData.accounts.map((acc) => {
                const accId = acc.id || acc.account_id || acc.customer_id;
                const accName = acc.name || acc.display_name || `Account ${accId}`;
                const accCurr = (acc.currency || storeCurrency).toUpperCase();
                const isSelected = Boolean(acc.is_selected);
                const isMismatch = Boolean(acc.currency_mismatch);

                return (
                  <div
                    key={accId}
                    onClick={() => handleAccountSelect(acc)}
                    className={`flex items-center justify-between p-2.5 rounded-md border cursor-pointer transition-colors ${
                      isSelected
                        ? "border-emerald-500/50 bg-emerald-500/10 text-[#F8FAFC]"
                        : "border-[#1E2235] bg-[#0A0C12] hover:border-[#2D334B] text-[#CBD5E1]"
                    }`}
                    data-testid={`${platform}-account-item-${accId}`}
                  >
                    <div className="flex items-center gap-2.5">
                      <div
                        className={`w-3.5 h-3.5 rounded-full border flex items-center justify-center ${
                          isSelected
                            ? "border-emerald-400 bg-emerald-500"
                            : "border-[#475569] bg-transparent"
                        }`}
                      >
                        {isSelected && <Check size={10} className="text-black stroke-[3]" />}
                      </div>
                      <div>
                        <div className="flex items-center gap-1.5">
                          <span className="font-medium text-xs text-[#F8FAFC]">
                            {accName}
                          </span>
                          {acc.is_manager && (
                            <span className="px-1.5 py-0.2 rounded bg-cyan-500/10 text-cyan-400 text-[10px] border border-cyan-500/20">
                              Manager
                            </span>
                          )}
                        </div>
                        <span className="text-[11px] text-[#64748B]">ID: {accId}</span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                          isMismatch
                            ? "bg-amber-500/10 text-amber-300 border border-amber-500/20"
                            : "bg-[#161926] text-[#94A3B8]"
                        }`}
                      >
                        {accCurr}
                      </span>
                      {isSelected && (
                        <span className="text-[11px] font-semibold text-emerald-400">
                          Active
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="py-4 text-center text-[#64748B]">
              <p>No ad accounts found for this identity.</p>
              <p className="mt-1 text-[11px]">
                Ensure your account has proper campaign management permissions.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
