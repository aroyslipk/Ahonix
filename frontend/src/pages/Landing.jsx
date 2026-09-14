import React from "react";
import { Link } from "react-router-dom";
import {
  Sparkles, ArrowRight, BrainCircuit, TrendingUp, ShieldCheck, Zap, LineChart, Boxes,
} from "lucide-react";
import { Logo } from "@/components/Logo";

const LOOP = ["Connect", "Understand", "Detect", "Explain", "Simulate", "Recommend", "Approve", "Execute", "Measure"];

const FEATURES = [
  { icon: BrainCircuit, title: "Business X-Ray", desc: "Scan your entire business and surface money leaks, growth opportunities and risks — with confidence scores." },
  { icon: TrendingUp, title: "True Profit Engine", desc: "Revenue minus ads, shipping, fees, returns and discounts. Know your real profit, per product." },
  { icon: LineChart, title: "Ask AHONIX ✦", desc: "A commerce analyst, not a chatbot. Ask why profit dropped or what to restock — get evidence and impact." },
  { icon: Boxes, title: "Forecasts & Simulations", desc: "Stock-out forecasts, market-entry simulations and safe, sandboxed action execution." },
];

export default function Landing() {
  return (
    <div className="min-h-screen bg-[#08090E] text-[#F8FAFC]">
      <header className="sticky top-0 z-30 border-b border-[#1E2235] bg-[#08090E]/85 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
          <Logo size={26} />
          <div className="flex items-center gap-3">
            <Link to="/login" className="text-sm font-medium text-[#94A3B8] hover:text-[#F8FAFC]" data-testid="landing-login">
              Sign in
            </Link>
            <Link
              to="/register"
              className="flex items-center gap-1.5 rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-emerald-950 hover:bg-emerald-400"
              data-testid="landing-get-started"
            >
              Get started <ArrowRight size={14} />
            </Link>
          </div>
        </div>
      </header>

      <section className="relative overflow-hidden px-6 py-24">
        <div
          className="pointer-events-none absolute inset-0 opacity-60"
          style={{
            background:
              "radial-gradient(700px circle at 50% -10%, rgba(16,185,129,0.12), transparent 55%), radial-gradient(500px circle at 85% 30%, rgba(6,182,212,0.08), transparent 45%)",
          }}
        />
        <div className="relative mx-auto max-w-4xl text-center">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-[#1E2235] bg-[#0F111A] px-4 py-1.5 text-xs font-medium text-[#94A3B8]">
            <Sparkles size={13} className="text-emerald-400" /> The AI Commerce OS
          </div>
          <h1 className="font-display text-4xl font-extrabold leading-[1.05] tracking-tight sm:text-5xl lg:text-6xl">
            Don't just see your data.
            <br />
            <span className="bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent">
              Know what to do next.
            </span>
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-[#94A3B8]">
            AHONIX connects your commerce data, finds where you lose money and where you can grow, explains why,
            and recommends the next best action — with projected financial impact.
          </p>
          <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link
              to="/register"
              className="flex items-center gap-2 rounded-xl bg-emerald-500 px-6 py-3 text-sm font-semibold text-emerald-950 shadow-lg shadow-emerald-500/20 transition-transform hover:scale-[1.03]"
              data-testid="hero-cta"
            >
              Explore the demo workspace <ArrowRight size={16} />
            </Link>
            <Link
              to="/login"
              className="rounded-xl border border-[#2D334B] px-6 py-3 text-sm font-semibold text-[#F8FAFC] hover:bg-[#161926]"
            >
              Sign in
            </Link>
          </div>

          <div className="mt-14 flex flex-wrap items-center justify-center gap-2">
            {LOOP.map((s, i) => (
              <React.Fragment key={s}>
                <span className="rounded-lg border border-[#1E2235] bg-[#0F111A] px-3 py-1.5 text-xs font-medium text-[#CBD5E1]">
                  {s}
                </span>
                {i < LOOP.length - 1 && <ArrowRight size={12} className="text-[#334155]" />}
              </React.Fragment>
            ))}
          </div>
        </div>
      </section>

      <section className="px-6 pb-24">
        <div className="mx-auto grid max-w-6xl gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {FEATURES.map((f) => (
            <div key={f.title} className="rounded-2xl border border-[#1E2235] bg-[#121420] p-6 card-hover">
              <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-400">
                <f.icon size={20} />
              </span>
              <h3 className="mt-4 font-display text-base font-bold">{f.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-[#94A3B8]">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="border-t border-[#1E2235] px-6 py-20">
        <div className="mx-auto flex max-w-4xl flex-col items-center gap-6 rounded-3xl border border-[#1E2235] bg-gradient-to-br from-[#0F111A] to-[#121420] p-12 text-center">
          <ShieldCheck className="text-emerald-400" size={30} />
          <h2 className="font-display text-2xl font-bold sm:text-3xl">Try it with zero setup</h2>
          <p className="max-w-xl text-[#94A3B8]">
            Spin up the <span className="font-semibold text-[#F8FAFC]">Northstar Goods</span> demo workspace — realistic,
            internally consistent data across sales, profit, inventory, marketing and returns.
          </p>
          <Link
            to="/register"
            className="flex items-center gap-2 rounded-xl bg-emerald-500 px-6 py-3 text-sm font-semibold text-emerald-950 hover:bg-emerald-400"
            data-testid="footer-cta"
          >
            <Zap size={16} /> Launch demo workspace
          </Link>
        </div>
      </section>

      <footer className="border-t border-[#1E2235] px-6 py-8">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 sm:flex-row">
          <Logo size={20} />
          <div className="flex items-center gap-6 text-xs text-[#64748B]">
            <Link to="/privacy" className="transition-colors hover:text-[#94A3B8]" data-testid="landing-privacy-link">
              Privacy Policy
            </Link>
            <Link to="/terms" className="transition-colors hover:text-[#94A3B8]" data-testid="landing-terms-link">
              Terms of Service
            </Link>
          </div>
          <p className="text-xs text-[#475569]">© 2026 AHONIX · The AI Commerce OS</p>
        </div>
      </footer>
    </div>
  );
}
