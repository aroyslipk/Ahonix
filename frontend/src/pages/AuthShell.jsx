import React from "react";
import { ShieldCheck, CheckCircle2, Lock, Zap, Award } from "lucide-react";
import { Logo } from "@/components/Logo";

export function AuthShell({ title, subtitle, children, footer }) {
  return (
    <div className="flex min-h-screen bg-[#040706] text-[#F8FAFC]">
      {/* Left Brand Panel - Cinematic 3D Identity (Desktop) */}
      <div className="relative hidden w-1/2 flex-col justify-between overflow-hidden border-r border-[#16221B] bg-[#070C0A] p-10 xl:p-14 lg:flex select-none">
        {/* Background Atmosphere & Oversized Wordmark */}
        <div
          className="pointer-events-none absolute inset-0 opacity-40"
          style={{
            background:
              "radial-gradient(800px circle at 20% 15%, rgba(0, 229, 153, 0.15), transparent 50%), radial-gradient(600px circle at 80% 85%, rgba(0, 229, 153, 0.08), transparent 50%)",
          }}
        />
        <div
          className="pointer-events-none absolute -bottom-12 -left-10 select-none font-display text-[170px] font-black tracking-tighter text-white/[0.02]"
          aria-hidden="true"
        >
          AHONIX
        </div>

        {/* Top Header */}
        <div className="relative z-10 flex items-center justify-between">
          <Logo size={32} />
          <span className="rounded-full border border-[#16221B] bg-[#0B1410] px-3.5 py-1 font-mono text-[10px] font-semibold tracking-wider text-[#00E599] uppercase">
            COMMERCE OS v2.4
          </span>
        </div>

        {/* Hero 3D Emblem & Centerpiece */}
        <div className="relative z-10 max-w-lg py-6">
          {/* 3D Emblem with volumetric aura & floating telemetry badges */}
          <div className="relative mb-8 flex h-52 w-52 items-center justify-center">
            <div className="absolute inset-0 rounded-full bg-[#00E599]/15 blur-3xl" />
            <img
              src="/ahonix-a-isolated.png"
              alt="AHONIX 3D Monogram"
              className="relative z-10 h-48 w-48 object-contain drop-shadow-[0_25px_50px_rgba(0,0,0,0.95)] filter transition-transform duration-700 hover:scale-105"
            />
            {/* Floating metric chip */}
            <div className="absolute -right-16 top-6 z-20 flex items-center gap-2 rounded-xl border border-[#16221B] bg-[#070C0A]/90 px-3 py-1.5 shadow-xl backdrop-blur-md">
              <span className="h-2 w-2 rounded-full bg-[#00E599] animate-pulse" />
              <span className="font-mono text-[11px] font-medium text-[#F8FAFC]">
                99.9% Margin Accuracy
              </span>
            </div>
          </div>

          <h1 className="font-display text-4xl font-extrabold leading-[1.15] tracking-tight text-[#F8FAFC]">
            Turn Your Commerce <br />
            <span className="text-[#00E599]">Into Real Profit.</span>
          </h1>

          <p className="mt-4 text-sm leading-relaxed text-[#94A3B8]">
            AHONIX is the commerce operating system that unifies your revenue, unit costs, ad spend, and inventory into single-pane deterministic net profit.
          </p>

          <div className="mt-8 space-y-3.5">
            {[
              "Verified True Profit reconciliation across every unit fee",
              "Autonomous money leak & margin erosion detection",
              "Sandboxed decision simulator before committing capital",
            ].map((t) => (
              <div key={t} className="flex items-center gap-3 text-xs text-[#CBD5E1]">
                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-[#00E599]/30 bg-[#00E599]/15 text-[#00E599]">
                  <CheckCircle2 size={12} />
                </span>
                <span>{t}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Bottom Trust Stamp */}
        <div className="relative z-10 flex items-center justify-between border-t border-[#16221B] pt-4 text-xs text-[#64748B]">
          <span className="flex items-center gap-1.5">
            <ShieldCheck size={14} className="text-[#00E599]" />
            Zero-Fabrication Commerce Engine
          </span>
          <span className="font-mono text-[11px]">SOC-2 Type II Certified</span>
        </div>
      </div>

      {/* Right Form Panel */}
      <div className="flex w-full flex-col justify-center px-4 py-10 sm:px-8 lg:w-1/2 lg:px-16 xl:px-24">
        <div className="mx-auto w-full max-w-md">
          {/* Mobile Header */}
          <div className="mb-6 flex items-center justify-between lg:hidden">
            <Logo size={28} />
            <span className="rounded-full border border-[#16221B] bg-[#070C0A] px-2.5 py-1 font-mono text-[9px] font-semibold text-[#00E599]">
              AI COMMERCE OS
            </span>
          </div>

          {/* Elevated Luxury Glass Card */}
          <div className="relative overflow-hidden rounded-2xl sm:rounded-3xl border border-[#16221B] bg-[#070C0A]/95 p-5 sm:p-9 shadow-2xl shadow-black/80 backdrop-blur-xl">
            {/* Top emerald reflection rim */}
            <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-[#00E599]/40 to-transparent" />

            <h2 className="font-display text-2xl sm:text-3xl font-bold tracking-tight text-[#F8FAFC]">
              {title}
            </h2>
            {subtitle && (
              <p className="mt-2 text-xs sm:text-sm leading-relaxed text-[#94A3B8]">
                {subtitle}
              </p>
            )}

            <div className="mt-6">{children}</div>

            {footer && (
              <div className="mt-6 text-center text-xs text-[#94A3B8] border-t border-[#16221B]/80 pt-5">
                {footer}
              </div>
            )}
          </div>

          {/* Security footnote */}
          <div className="mt-6 flex items-center justify-center gap-2 text-center px-2 text-[10px] sm:text-[11px] text-[#64748B]">
            <Lock size={12} className="shrink-0 text-[#00E599]" />
            <span>256-Bit TLS Encryption · Read-Only By Default · Zero Fabrication</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export function GoogleButton({ label = "Continue with Google" }) {
  const [checking, setChecking] = React.useState(false);

  const onClick = async () => {
    const isEmergent =
      typeof window !== "undefined" &&
      window.location.hostname.endsWith(".preview.emergentagent.com");

    const redirectUrl = window.location.origin + "/app/overview";

    if (isEmergent) {
      window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
      return;
    }

    // Direct Google OAuth flow for Staging and Production
    const rawBackendUrl = process.env.REACT_APP_BACKEND_URL;
    const backendUrl = rawBackendUrl ? rawBackendUrl.replace(/\/$/, "") : "";

    setChecking(true);
    try {
      const res = await fetch(`${backendUrl}/api/auth/google/status`);
      if (res.ok) {
        const data = await res.json();
        if (data.configured === false) {
          alert("Google OAuth is not configured on this server (GOOGLE_CLIENT_ID missing in Render environment variables). Please sign in using email and password, or add GOOGLE_CLIENT_ID to Render.");
          setChecking(false);
          return;
        }
      }
    } catch {
      // Proceed to standard backend redirect if probe is inconclusive
    }
    setChecking(false);

    window.location.href = `${backendUrl}/api/auth/google/login?redirect=${encodeURIComponent("/app/overview")}`;
  };

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={checking}
      className="flex w-full items-center justify-center gap-3 rounded-xl border border-[#16221B] bg-[#0B110E] py-3 text-xs font-semibold text-[#F8FAFC] transition-all duration-150 hover:border-[#00E599]/40 hover:bg-[#0F1713] disabled:opacity-50"
      data-testid="google-auth-btn"
    >
      <svg width="18" height="18" viewBox="0 0 24 24">
        <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" />
        <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23z" />
        <path fill="#FBBC05" d="M5.84 14.1a6.6 6.6 0 0 1 0-4.2V7.06H2.18a11 11 0 0 0 0 9.88l3.66-2.84z" />
        <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84C6.71 7.3 9.14 5.38 12 5.38z" />
      </svg>
      {checking ? "Checking Google Auth..." : label}
    </button>
  );
}
