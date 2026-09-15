import React from "react";
import { Logo } from "@/components/Logo";

export function AuthShell({ title, subtitle, children, footer }) {
  return (
    <div className="flex min-h-screen bg-[#08090E]">
      {/* left brand panel */}
      <div className="relative hidden w-1/2 flex-col justify-between overflow-hidden border-r border-[#1E2235] bg-[#0B0D14] p-12 lg:flex">
        <div
          className="pointer-events-none absolute inset-0 opacity-40"
          style={{
            background:
              "radial-gradient(600px circle at 20% 15%, rgba(16,185,129,0.14), transparent 45%), radial-gradient(500px circle at 80% 80%, rgba(6,182,212,0.1), transparent 45%)",
          }}
        />
        <Logo size={30} />
        <div className="relative z-10 max-w-md">
          <h1 className="font-display text-4xl font-extrabold leading-tight tracking-tight text-[#F8FAFC]">
            Stop guessing.
            <br />
            <span className="text-emerald-400">Know what to do next.</span>
          </h1>
          <p className="mt-4 text-base leading-relaxed text-[#94A3B8]">
            AHONIX connects your commerce data, finds where you lose money and where you can grow, then
            recommends the next best action — with projected impact.
          </p>
          <div className="mt-8 space-y-3">
            {["Detect money leaks & growth opportunities", "True profit after every hidden cost", "Simulate actions before you commit"].map(
              (t) => (
                <div key={t} className="flex items-center gap-3 text-sm text-[#CBD5E1]">
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500/15 text-emerald-400">
                    ✓
                  </span>
                  {t}
                </div>
              )
            )}
          </div>
        </div>
        <p className="relative z-10 text-xs text-[#475569]">The AI Commerce OS · Demo workspace included</p>
      </div>

      {/* right form panel */}
      <div className="flex w-full flex-col justify-center px-6 py-12 lg:w-1/2 lg:px-20">
        <div className="mx-auto w-full max-w-sm">
          <div className="mb-8 lg:hidden">
            <Logo size={26} />
          </div>
          <h2 className="font-display text-2xl font-bold text-[#F8FAFC]">{title}</h2>
          {subtitle && <p className="mt-2 text-sm text-[#94A3B8]">{subtitle}</p>}
          <div className="mt-8">{children}</div>
          {footer && <div className="mt-6 text-center text-sm text-[#94A3B8]">{footer}</div>}
        </div>
      </div>
    </div>
  );
}

export function GoogleButton({ label = "Continue with Google" }) {
  const onClick = () => {
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
    window.location.href = `${backendUrl}/api/auth/google/login?redirect=${encodeURIComponent("/app/overview")}`;
  };
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-center justify-center gap-3 rounded-lg border border-[#2D334B] bg-[#0F111A] py-2.5 text-sm font-medium text-[#F8FAFC] transition-colors hover:bg-[#161926]"
      data-testid="google-auth-btn"
    >
      <svg width="18" height="18" viewBox="0 0 24 24">
        <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" />
        <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23z" />
        <path fill="#FBBC05" d="M5.84 14.1a6.6 6.6 0 0 1 0-4.2V7.06H2.18a11 11 0 0 0 0 9.88l3.66-2.84z" />
        <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84C6.71 7.3 9.14 5.38 12 5.38z" />
      </svg>
      {label}
    </button>
  );
}
