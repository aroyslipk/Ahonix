import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowRight, ArrowLeft, Check, Loader2, Sparkles, Store, ShoppingBag,
  Globe, Wallet, Database, Rocket, Building2,
} from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Logo } from "@/components/Logo";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

const BUSINESS_TYPES = ["DTC Brand", "Marketplace Seller", "Agency", "Dropshipping", "Wholesale / B2B", "Omnichannel Retail"];
const CHANNELS = ["Shopify", "Amazon", "WooCommerce", "Etsy", "TikTok Shop", "eBay", "Own website"];
const SIZES = ["Just starting (<$10k/mo)", "Growing ($10k–$100k/mo)", "Scaling ($100k–$1M/mo)", "Established ($1M+/mo)"];
const COUNTRIES = ["United States", "United Kingdom", "Germany", "Canada", "Australia", "France", "India", "Other"];
const CURRENCIES = [
  { code: "USD", label: "US Dollar ($)" },
  { code: "EUR", label: "Euro (€)" },
  { code: "GBP", label: "British Pound (£)" },
  { code: "CAD", label: "Canadian Dollar (C$)" },
  { code: "AUD", label: "Australian Dollar (A$)" },
  { code: "INR", label: "Indian Rupee (₹)" },
];

function Chip({ active, children, onClick, testid }) {
  return (
    <button
      type="button"
      onClick={onClick}
      data-testid={testid}
      className={`rounded-xl border px-4 py-3 text-left text-sm font-medium transition-all ${
        active
          ? "border-emerald-500 bg-emerald-500/10 text-emerald-200"
          : "border-[#2D334B] bg-[#0F111A] text-[#CBD5E1] hover:border-[#3D4560]"
      }`}
    >
      <span className="flex items-center justify-between gap-2">
        {children}
        {active && <Check size={15} className="text-emerald-400" />}
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
    size: SIZES[2],
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
      icon: Sparkles,
      title: `Welcome to AHONIX, ${(user?.name || "there").split(" ")[0]} 👋`,
      subtitle: "Let's set up your command center. It takes under a minute.",
      body: (
        <div className="rounded-2xl border border-[#1E2235] bg-[#0F111A] p-6">
          <p className="text-sm leading-relaxed text-[#CBD5E1]">
            AHONIX is your <span className="font-semibold text-emerald-300">AI Commerce OS</span>. We'll ask a few
            quick questions, then you can explore a fully-loaded demo workspace — no data connection required.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            {["Detect money leaks", "True profit", "AI recommendations", "Safe simulations"].map((t) => (
              <span key={t} className="rounded-lg bg-[#161926] px-3 py-1.5 text-xs text-[#94A3B8]">{t}</span>
            ))}
          </div>
        </div>
      ),
    },
    {
      icon: Store, title: "What's your store called?", subtitle: "This names your workspace.",
      body: (
        <Input
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
          placeholder="e.g. Northstar Goods"
          className="border-[#2D334B] bg-[#0F111A] text-lg text-[#F8FAFC]"
          data-testid="onboarding-store-name"
        />
      ),
    },
    {
      icon: Building2, title: "What type of business is it?", subtitle: "Pick the closest match.",
      body: (
        <div className="grid grid-cols-2 gap-2">
          {BUSINESS_TYPES.map((t) => (
            <Chip key={t} active={form.business_type === t} onClick={() => setForm({ ...form, business_type: t })}>{t}</Chip>
          ))}
        </div>
      ),
    },
    {
      icon: ShoppingBag, title: "Primary sales channels", subtitle: "Select all that apply.",
      body: (
        <div className="grid grid-cols-2 gap-2">
          {CHANNELS.map((c) => (
            <Chip key={c} active={form.channels.includes(c)} onClick={() => toggleChannel(c)}>{c}</Chip>
          ))}
        </div>
      ),
    },
    {
      icon: TrendingWrapper, title: "How big is your business?", subtitle: "Monthly revenue range.",
      body: (
        <div className="grid gap-2">
          {SIZES.map((s) => (
            <Chip key={s} active={form.size === s} onClick={() => setForm({ ...form, size: s })}>{s}</Chip>
          ))}
        </div>
      ),
    },
    {
      icon: Globe, title: "Where are you based?", subtitle: "Your primary market.",
      body: (
        <div className="grid grid-cols-2 gap-2">
          {COUNTRIES.map((c) => (
            <Chip key={c} active={form.country === c} onClick={() => setForm({ ...form, country: c })}>{c}</Chip>
          ))}
        </div>
      ),
    },
    {
      icon: Wallet, title: "Preferred currency", subtitle: "Used across all metrics.",
      body: (
        <div className="grid grid-cols-2 gap-2">
          {CURRENCIES.map((c) => (
            <Chip key={c.code} active={form.currency === c.code} onClick={() => setForm({ ...form, currency: c.code })}>{c.label}</Chip>
          ))}
        </div>
      ),
    },
    {
      icon: Rocket, title: "You're all set", subtitle: "Choose how you'd like to start.",
      body: (
        <div className="grid gap-4">
          <button
            onClick={() => finish("demo")}
            disabled={submitting}
            className="group rounded-2xl border border-emerald-500/40 bg-emerald-500/5 p-5 text-left transition-all hover:border-emerald-500 hover:bg-emerald-500/10"
            data-testid="onboarding-demo-btn"
          >
            <div className="flex items-center gap-3">
              <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-500/15 text-emerald-400">
                {submitting ? <Loader2 className="animate-spin" size={20} /> : <Sparkles size={20} />}
              </span>
              <div className="flex-1">
                <p className="font-display font-bold text-[#F8FAFC]">Explore Demo Workspace</p>
                <p className="text-sm text-[#94A3B8]">Realistic data for {form.name}. Recommended.</p>
              </div>
              <ArrowRight className="text-emerald-400 transition-transform group-hover:translate-x-1" size={18} />
            </div>
          </button>

          <button
            onClick={() => finish("real")}
            disabled={submitting}
            className="group rounded-2xl border border-[#2D334B] bg-[#0F111A] p-5 text-left transition-all hover:border-[#3D4560]"
            data-testid="onboarding-real-btn"
          >
            <div className="flex items-center gap-3">
              <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-[#161926] text-[#94A3B8]">
                <Database size={20} />
              </span>
              <div className="flex-1">
                <p className="font-display font-bold text-[#F8FAFC]">Connect my real data</p>
                <p className="text-sm text-[#94A3B8]">Set up integrations later from Settings.</p>
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
    <div className="flex min-h-screen items-center justify-center bg-[#08090E] px-4 py-10">
      <div className="w-full max-w-lg">
        <div className="mb-8 flex items-center justify-between">
          <Logo size={24} />
          <span className="text-xs text-[#64748B]">Step {step + 1} of {steps.length}</span>
        </div>

        <div className="mb-6 h-1.5 w-full overflow-hidden rounded-full bg-[#161926]">
          <div
            className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-cyan-500 transition-all duration-500"
            style={{ width: `${((step + 1) / steps.length) * 100}%` }}
          />
        </div>

        <div className="rounded-3xl border border-[#1E2235] bg-[#121420] p-7" data-testid="onboarding-wizard-step">
          <span className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-400">
            <Icon size={20} />
          </span>
          <h1 className="font-display text-2xl font-bold text-[#F8FAFC]">{current.title}</h1>
          <p className="mt-1.5 text-sm text-[#94A3B8]">{current.subtitle}</p>
          <div className="mt-6">{current.body}</div>

          {!isLast && (
            <div className="mt-8 flex items-center justify-between">
              <Button
                variant="ghost"
                onClick={() => setStep((s) => Math.max(0, s - 1))}
                disabled={step === 0}
                className="text-[#94A3B8] hover:bg-[#161926] hover:text-[#F8FAFC] disabled:opacity-0"
                data-testid="onboarding-back"
              >
                <ArrowLeft size={16} className="mr-1" /> Back
              </Button>
              <Button
                onClick={() => setStep((s) => s + 1)}
                className="bg-emerald-500 font-semibold text-emerald-950 hover:bg-emerald-400"
                data-testid="onboarding-next"
              >
                Continue <ArrowRight size={16} className="ml-1" />
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// small inline icon wrapper to avoid extra import name clash
function TrendingWrapper(props) {
  return (
    <svg {...props} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 3v18h18" />
      <path d="m19 9-5 5-4-4-3 3" />
    </svg>
  );
}
