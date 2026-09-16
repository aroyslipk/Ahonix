import React, { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Loader2, Mail, Lock, Eye, EyeOff, ArrowRight } from "lucide-react";
import { api, formatApiErrorDetail } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { AuthShell, GoogleButton } from "@/pages/AuthShell";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";

export default function Login() {
  const [email, setEmail] = useState("alex@northstargoods.com");
  const [password, setPassword] = useState("Ahonix2026!");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [unverifiedEmail, setUnverifiedEmail] = useState(null);
  const [resending, setResending] = useState(false);
  const [resendSuccess, setResendSuccess] = useState(false);
  const { setUser } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const err = params.get("error");
    if (err) {
      setError(err);
    }
  }, []);

  const handleResendVerification = async () => {
    if (!unverifiedEmail) return;
    setResending(true);
    try {
      await api.post("/auth/resend-verification", { email: unverifiedEmail });
      setResendSuccess(true);
      toast.success("Verification link sent! Check your inbox.");
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || "Failed to resend verification email.");
    } finally {
      setResending(false);
    }
  };

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setUnverifiedEmail(null);
    setResendSuccess(false);
    setLoading(true);
    try {
      const { data } = await api.post("/auth/login", { email, password });
      setUser(data);
      navigate(data.onboarding_completed ? "/app/overview" : "/onboarding", { replace: true });
    } catch (err) {
      const detail = err.response?.data?.detail;
      const isUnverified = err.response?.status === 403 && (
        detail?.code === "EMAIL_NOT_VERIFIED" ||
        (typeof detail === "string" && detail.includes("not been verified")) ||
        (detail?.message && detail.message.includes("not been verified"))
      );
      if (isUnverified) {
        setUnverifiedEmail(detail?.email || email);
        setError("Your email address has not been verified yet. Please check your inbox or resend verification.");
      } else {
        setError(formatApiErrorDetail(detail) || err.message);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell
      title="Welcome back"
      subtitle="Sign in to your AHONIX command center."
      footer={
        <>
          New to AHONIX?{" "}
          <Link
            to="/register"
            className="font-bold text-[#00E599] hover:underline"
            data-testid="link-register"
          >
            Create an account
          </Link>
        </>
      }
    >
      <form onSubmit={submit} className="space-y-4" data-testid="login-form">
        {unverifiedEmail ? (
          <div
            className="rounded-xl border border-amber-500/40 bg-amber-950/20 p-3.5 text-xs text-amber-200"
            data-testid="unverified-email-notice"
          >
            <div className="flex items-start gap-2.5">
              <Mail size={16} className="shrink-0 mt-0.5 text-amber-400" />
              <div className="flex-1">
                <p className="font-semibold text-amber-100">Email Verification Required</p>
                <p className="mt-1 text-[11px] text-amber-200/90 leading-relaxed">
                  We sent a verification link to <strong>{unverifiedEmail}</strong>. Please confirm your email address to log in.
                </p>
                {resendSuccess ? (
                  <p className="mt-2 text-[11px] font-semibold text-[#00E599]">
                    ✓ Fresh verification link sent! Please check your inbox.
                  </p>
                ) : (
                  <button
                    type="button"
                    disabled={resending}
                    onClick={handleResendVerification}
                    className="mt-2 inline-flex items-center gap-1 font-semibold text-[#00E599] hover:underline disabled:opacity-50"
                    data-testid="resend-unverified-btn"
                  >
                    {resending ? "Sending link..." : "Resend verification link →"}
                  </button>
                )}
              </div>
            </div>
          </div>
        ) : error ? (
          <div
            className="rounded-xl border border-rose-900/50 bg-rose-950/30 px-3.5 py-2.5 text-xs text-rose-300"
            data-testid="login-error"
          >
            {error}
          </div>
        ) : null}

        {/* Email */}
        <div>
          <Label className="text-xs font-semibold text-[#94A3B8]">Email Address</Label>
          <div className="relative mt-1.5">
            <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-[#64748B]">
              <Mail size={15} />
            </div>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="h-11 w-full rounded-xl border border-[#16221B] bg-[#0B110E] pl-10 pr-3.5 text-xs text-[#F8FAFC] placeholder:text-[#475569] transition-all focus:border-[#00E599] focus:outline-none focus:ring-1 focus:ring-[#00E599]/30"
              data-testid="login-email"
            />
          </div>
        </div>

        {/* Password */}
        <div>
          <div className="flex items-center justify-between">
            <Label className="text-xs font-semibold text-[#94A3B8]">Password</Label>
            <Link
              to="/forgot-password"
              className="text-xs font-medium text-[#00E599] hover:underline"
              data-testid="link-forgot"
            >
              Forgot password?
            </Link>
          </div>
          <div className="relative mt-1.5">
            <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-[#64748B]">
              <Lock size={15} />
            </div>
            <input
              type={showPassword ? "text" : "password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="h-11 w-full rounded-xl border border-[#16221B] bg-[#0B110E] pl-10 pr-10 text-xs text-[#F8FAFC] placeholder:text-[#475569] transition-all focus:border-[#00E599] focus:outline-none focus:ring-1 focus:ring-[#00E599]/30"
              data-testid="login-password"
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute inset-y-0 right-0 flex items-center pr-3.5 text-[#64748B] hover:text-[#94A3B8]"
              aria-label={showPassword ? "Hide password" : "Show password"}
            >
              {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
            </button>
          </div>
        </div>

        {/* Submit */}
        <button
          type="submit"
          disabled={loading}
          className="mt-2 flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-[#00E599] font-display text-xs font-bold text-[#040706] shadow-lg shadow-[#00E599]/20 transition-all hover:bg-[#00c984] hover:scale-[1.01] active:scale-[0.99] disabled:opacity-50"
          data-testid="login-submit"
        >
          {loading ? (
            <Loader2 className="animate-spin" size={16} />
          ) : (
            <>
              Sign In to AHONIX <ArrowRight size={14} />
            </>
          )}
        </button>
      </form>

      {/* Divider */}
      <div className="my-5 flex items-center gap-3 text-[11px] font-mono text-[#475569]">
        <div className="h-px flex-1 bg-[#16221B]" />
        <span>OR</span>
        <div className="h-px flex-1 bg-[#16221B]" />
      </div>

      <GoogleButton />

      <p className="mt-4 rounded-xl border border-[#16221B] bg-[#0B110E] px-3.5 py-2 text-center text-[11px] text-[#64748B]">
        Demo merchant credentials prefilled · instant exploratory access
      </p>

      <div className="mt-5 flex items-center justify-center gap-4 text-xs text-[#64748B]">
        <Link
          to="/privacy"
          className="transition-colors hover:text-[#94A3B8] hover:underline"
          data-testid="login-privacy-link"
        >
          Privacy Policy
        </Link>
        <span>·</span>
        <Link
          to="/terms"
          className="transition-colors hover:text-[#94A3B8] hover:underline"
          data-testid="login-terms-link"
        >
          Terms of Service
        </Link>
      </div>
    </AuthShell>
  );
}
