import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowRight,
  ArrowLeft,
  Check,
  Loader2,
  Compass,
  Store,
  ShoppingBag,
  Globe,
  Wallet,
  Database,
  Rocket,
  Building2,
  CheckCircle2,
  TrendingUp,
} from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Logo } from "@/components/Logo";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

const BUSINESS_TYPES = [
  "DTC Brand",
  "Marketplace Seller",
  "Commerce Agency",
  "Cross-border / Wholesale",
  "Omnichannel Enterprise",
  "High-Growth Startup",
];

const CHANNELS = [
  "Shopify",
  "Amazon",
  "WooCommerce",
  "TikTok Shop",
  "Meta Commerce",
  "Google Merchant",
  "Custom Headless API",
];

const SIZES = [
  "Emerging (<$25k/mo)",
  "Scaling ($25k–$100k/mo)",
  "Mid-Market ($100k–$500k/mo)",
  "Enterprise ($500k+/mo)",
];

const COUNTRIES = [
  "United States",
  "United Kingdom",
  "European Union",
  "Canada",
  "Australia",
  "Singapore",
  "Global / Multi-Region",
];

const CURRENCIES = [
  { code: "USD", label: "US Dollar ($)" },
  { code: "EUR", label: "Euro (€)" },
  { code: "GBP", label: "British Pound (£)" },
  { code: "CAD", label: "Canadian Dollar (C$)" },
  { code: "AUD", label: "Australian Dollar (A$)" },
  { code: "SGD", label: "Singapore Dollar (S$)" },
];

function Chip({ active, children, onClick, testid }) {
  return (
    <button
      type="button"
      onClick={onClick}
      data-testid={testid}
      className={`rounded-xl border px-3.5 py-2.5 sm:px-4 sm:py-3 text-left text-xs font-semibold transition-all ${
        active
          ? "border-[#00E599] bg-[#00E599]/10 text-[#00E599] shadow-[0_0_15px_rgba(0,229,153,0.1)]"
          : "border-[#16221B] bg-[#070C0A] text-[#CBD5E1] hover:border-[#1F3327] hover:bg-[#0B110E]"
      }`}
    >
      <span className="flex items-center justify-between gap-2">
        {children}
        {active && <Check size={14} className="text-[#00E599]" />}
      </span>
    </button>
  );
}

export default function Onboarding() {
  const { user, setUser } = useAuth();
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({
    name: "Northstar Goods",
    business_type: "DTC Brand",
    channels: ["Shopify", "Amazon"],
    size: SIZES[1],
    country: "United States",
    currency: "USD",
  });

  const toggleChannel = (c) =>
    setForm((f) => ({
      ...f,
      channels: f.channels.includes(c) ? f.channels.filter((x) => x !== c) : [...f.channels, c],
    }));

  const finish = async (mode) => {
    setSubmitting(true);
    try {
      await api.post("/workspaces", { ...form, mode });
      const { data } = await api.get("/auth/me");
      setUser(data);
      navigate("/app/overview", { replace: true });
    } catch {
      setSubmitting(false);
    }
  };

  const steps = [
    {
      icon: Compass,
      title: `Welcome to AHONIX, ${(user?.name || "Merchant").split(" ")[0]}`,
      subtitle: "Configure your operating parameters. Full deployment takes less than 60 seconds.",
      body: (
        <div className="rounded-2xl border border-[#16221B] bg-[#070C0A] p-6">
          <p className="text-xs leading-relaxed text-[#94A3B8]">
            AHONIX is the unified <span className="font-semibold text-[#00E599]">Commerce Operating System</span>.
            We will establish your workspace telemetry, calibrate financial definitions, and initialize your command surface.
          </p>
          <div className="mt-5 grid grid-cols-2 gap-2.5">
            {[
              "True Net Profit Waterfall",
              "COGS Reconciliation Engine",
              "Autonomous Money-Leak Detection",
              "Sandboxed Strategic Interventions",
            ].map((t) => (
              <div
                key={t}
                className="flex items-center gap-2 rounded-xl border border-[#16221B] bg-[#0B110E] px-3 py-2 text-[11px] font-medium text-[#CBD5E1]"
              >
                <CheckCircle2 size={13} className="shrink-0 text-[#00E599]" />
                <span>{t}</span>
              </div>
            ))}
          </div>
        </div>
      ),
    },
    {
      icon: Store,
      title: "What is your primary brand or store name?",
      subtitle: "This anchors your primary workspace and tenant identity.",
      body: (
        <Input
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
          placeholder="e.g. Northstar Goods"
          className="border-[#16221B] bg-[#070C0A] text-base text-[#F8FAFC] placeholder-[#64748B] focus:border-[#00E599] rounded-xl py-3 px-4"
          data-testid="onboarding-store-name"
        />
      ),
    },
    {
      icon: Building2,
      title: "Select your operating commerce model",
      subtitle: "Calibrates default margin thresholds and working capital benchmarks.",
      body: (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
          {BUSINESS_TYPES.map((t) => (
            <Chip key={t} active={form.business_type === t} onClick={() => setForm({ ...form, business_type: t })}>
              {t}
            </Chip>
          ))}
        </div>
      ),
    },
    {
      icon: ShoppingBag,
      title: "Active distribution channels",
      subtitle: "Select all storefronts and sales surfaces currently generating GMV.",
      body: (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
          {CHANNELS.map((c) => (
            <Chip key={c} active={form.channels.includes(c)} onClick={() => toggleChannel(c)}>
              {c}
            </Chip>
          ))}
        </div>
      ),
    },
    {
      icon: TrendingUp,
      title: "Current monthly GMV bracket",
      subtitle: "Enables benchmark-aligned anomaly thresholds and scale metrics.",
      body: (
        <div className="grid gap-2.5">
          {SIZES.map((s) => (
            <Chip key={s} active={form.size === s} onClick={() => setForm({ ...form, size: s })}>
              {s}
            </Chip>
          ))}
        </div>
      ),
    },
    {
      icon: Globe,
      title: "Primary jurisdiction & tax domicile",
      subtitle: "Sets baseline statutory currency and nexus parameters.",
      body: (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
          {COUNTRIES.map((c) => (
            <Chip key={c} active={form.country === c} onClick={() => setForm({ ...form, country: c })}>
              {c}
            </Chip>
          ))}
        </div>
      ),
    },
    {
      icon: Wallet,
      title: "Functional reporting currency",
      subtitle: "All sales, COGS, marketing spend, and net margins will reconcile in this currency.",
      body: (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
          {CURRENCIES.map((c) => (
            <Chip key={c.code} active={form.currency === c.code} onClick={() => setForm({ ...form, currency: c.code })}>
              {c.label}
            </Chip>
          ))}
        </div>
      ),
    },
    {
      icon: Rocket,
      title: "Ready to launch AHONIX",
      subtitle: "Choose your workspace deployment configuration.",
      body: (
        <div className="grid gap-3.5">
          <button
            onClick={() => finish("demo")}
            disabled={submitting}
            className="group rounded-2xl border border-emerald-500/30 bg-[#070C0A] p-5 text-left transition-all hover:border-[#00E599] hover:bg-[#00E599]/5"
            data-testid="onboarding-demo-btn"
          >
            <div className="flex items-center gap-3.5">
              <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-[#00E599]/15 text-[#00E599] border border-[#00E599]/30">
                {submitting ? <Loader2 className="animate-spin" size={20} /> : <Compass size={20} />}
              </span>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <p className="font-display text-sm font-bold text-[#F8FAFC]">Initialize Demo Command Center</p>
                  <span className="rounded-full border border-[#00E599]/30 bg-[#00E599]/10 px-2 py-0.5 text-[10px] font-semibold text-[#00E599]">
                    Recommended
                  </span>
                </div>
                <p className="mt-0.5 text-xs text-[#94A3B8]">
                  Full dataset preloaded for {form.name} with realistic orders, marketing spend, and margin leaks.
                </p>
              </div>
              <ArrowRight className="text-[#00E599] transition-transform group-hover:translate-x-1" size={18} />
            </div>
          </button>

          <button
            onClick={() => finish("real")}
            disabled={submitting}
            className="group rounded-2xl border border-[#16221B] bg-[#070C0A] p-5 text-left transition-all hover:border-[#1F3327] hover:bg-[#0B110E]"
            data-testid="onboarding-real-btn"
          >
            <div className="flex items-center gap-3.5">
              <span className="flex h-11 w-11 items-center justify-center rounded-xl border border-[#16221B] bg-[#0B110E] text-[#94A3B8]">
                <Database size={20} />
              </span>
              <div className="flex-1">
                <p className="font-display text-sm font-bold text-[#F8FAFC]">Connect Live Merchant Data</p>
                <p className="mt-0.5 text-xs text-[#64748B]">
                  Start with a pristine empty tenant and connect Shopify / Meta / Google Ads directly from Settings.
                </p>
              </div>
              <ArrowRight className="text-[#64748B] transition-transform group-hover:translate-x-1" size={18} />
            </div>
          </button>
        </div>
      ),
    },
  ];

  const current = steps[step];
  const isLast = step === steps.length - 1;
  const Icon = current.icon;

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#040706] px-4 py-12 relative overflow-hidden">
      {/* Background ambient lighting */}
      <div className="pointer-events-none absolute -top-40 left-1/2 -translate-x-1/2 h-[450px] w-[600px] rounded-full bg-emerald-500/5 blur-[120px]" />

      <div className="w-full max-w-xl relative z-10">
        <div className="mb-8 flex items-center justify-between">
          <Logo size={24} />
          <span className="rounded-lg border border-[#16221B] bg-[#070C0A] px-2.5 py-1 text-[11px] font-semibold text-[#64748B]">
            Step {step + 1} of {steps.length}
          </span>
        </div>

        {/* Progress track */}
        <div className="mb-6 h-1 w-full overflow-hidden rounded-full bg-[#121C16]">
          <div
            className="h-full rounded-full bg-[#00E599] transition-all duration-500"
            style={{ width: `${((step + 1) / steps.length) * 100}%` }}
          />
        </div>

        {/* Onboarding step card */}
        <div
          className="rounded-3xl border border-[#16221B] bg-[#070C0A] p-8 shadow-[0_20px_50px_rgba(0,0,0,0.5)]"
          data-testid="onboarding-wizard-step"
        >
          <div className="flex items-center gap-3 mb-4">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-emerald-500/20 bg-emerald-500/10 text-[#00E599]">
              <Icon size={18} />
            </span>
            <span className="text-[10px] font-semibold uppercase tracking-wider text-[#64748B]">
              Workspace Provisioning
            </span>
          </div>

          <h1 className="font-display text-xl font-bold text-[#F8FAFC] tracking-tight">
            {current.title}
          </h1>
          <p className="mt-1.5 text-xs text-[#94A3B8]">{current.subtitle}</p>
          <div className="mt-6">{current.body}</div>

          {!isLast && (
            <div className="mt-8 flex items-center justify-between border-t border-[#16221B] pt-5">
              <Button
                variant="ghost"
                onClick={() => setStep((s) => Math.max(0, s - 1))}
                disabled={step === 0}
                className="text-xs font-semibold text-[#94A3B8] hover:bg-[#0B110E] hover:text-[#F8FAFC] disabled:opacity-0"
                data-testid="onboarding-back"
              >
                <ArrowLeft size={15} className="mr-1.5" /> Previous
              </Button>
              <Button
                onClick={() => setStep((s) => s + 1)}
                className="rounded-xl bg-[#00E599] px-5 py-2.5 text-xs font-bold text-[#040706] hover:bg-[#00c984] shadow-[0_2px_10px_rgba(0,229,153,0.15)]"
                data-testid="onboarding-next"
              >
                Continue <ArrowRight size={15} className="ml-1.5" />
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
