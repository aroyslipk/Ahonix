import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Loader2, User, Mail, Lock, Eye, EyeOff, ArrowRight, CheckCircle2 } from "lucide-react";
import { api, formatApiErrorDetail } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { AuthShell, GoogleButton } from "@/pages/AuthShell";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

export default function Register() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { setUser } = useAuth();
  const navigate = useNavigate();

  // Password strength calculation
  const getPasswordStrength = () => {
    if (!password) return { level: 0, text: "" };
    let score = 0;
    if (password.length >= 6) score++;
    if (password.length >= 8 && /[A-Z]/.test(password)) score++;
    if (/\d/.test(password) || /[^A-Za-z0-9]/.test(password)) score++;
    if (score === 1) return { level: 1, text: "Weak", color: "bg-amber-500" };
    if (score === 2) return { level: 2, text: "Good", color: "bg-sky-400" };
    return { level: 3, text: "Strong", color: "bg-[#00E599]" };
  };

  const strength = getPasswordStrength();

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const { data } = await api.post("/auth/register", { name, email, password });
      setUser(data);
      navigate("/onboarding", { replace: true });
    } catch (err) {
      setError(formatApiErrorDetail(err.response?.data?.detail) || err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell
      title="Create your workspace"
      subtitle="Start with an instant live demo workspace — zero credit card required."
      footer={
        <>
          Already have an account?{" "}
          <Link
            to="/login"
            className="font-bold text-[#00E599] hover:underline"
            data-testid="link-login"
          >
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={submit} className="space-y-4" data-testid="register-form">
        {error && (
          <div
            className="rounded-xl border border-rose-900/50 bg-rose-950/30 px-3.5 py-2.5 text-xs text-rose-300"
            data-testid="register-error"
          >
            {error}
          </div>
        )}

        {/* Full Name */}
        <div>
          <Label className="text-xs font-semibold text-[#94A3B8]">Full Name</Label>
          <div className="relative mt-1.5">
            <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-[#64748B]">
              <User size={15} />
            </div>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              placeholder="Alex Northstar"
              className="h-11 w-full rounded-xl border border-[#16221B] bg-[#0B110E] pl-10 pr-3.5 text-xs text-[#F8FAFC] placeholder:text-[#475569] transition-all focus:border-[#00E599] focus:outline-none focus:ring-1 focus:ring-[#00E599]/30"
              data-testid="register-name"
            />
          </div>
        </div>

        {/* Work Email */}
        <div>
          <Label className="text-xs font-semibold text-[#94A3B8]">Work Email</Label>
          <div className="relative mt-1.5">
            <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-[#64748B]">
              <Mail size={15} />
            </div>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              placeholder="alex@northstargoods.com"
              className="h-11 w-full rounded-xl border border-[#16221B] bg-[#0B110E] pl-10 pr-3.5 text-xs text-[#F8FAFC] placeholder:text-[#475569] transition-all focus:border-[#00E599] focus:outline-none focus:ring-1 focus:ring-[#00E599]/30"
              data-testid="register-email"
            />
          </div>
        </div>

        {/* Password */}
        <div>
          <div className="flex items-center justify-between">
            <Label className="text-xs font-semibold text-[#94A3B8]">Password</Label>
            {password && (
              <span className="font-mono text-[10px] text-[#94A3B8]">
                {strength.text}
              </span>
            )}
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
              placeholder="At least 6 characters"
              className="h-11 w-full rounded-xl border border-[#16221B] bg-[#0B110E] pl-10 pr-10 text-xs text-[#F8FAFC] placeholder:text-[#475569] transition-all focus:border-[#00E599] focus:outline-none focus:ring-1 focus:ring-[#00E599]/30"
              data-testid="register-password"
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

          {/* Password strength mini bar */}
          {password && (
            <div className="mt-2 flex items-center gap-1.5">
              {[1, 2, 3].map((lvl) => (
                <div
                  key={lvl}
                  className={`h-1 flex-1 rounded-full transition-colors ${
                    strength.level >= lvl ? strength.color : "bg-[#16221B]"
                  }`}
                />
              ))}
            </div>
          )}
        </div>

        {/* Submit Button */}
        <button
          type="submit"
          disabled={loading}
          className="mt-2 flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-[#00E599] font-display text-xs font-bold text-[#040706] shadow-lg shadow-[#00E599]/20 transition-all hover:bg-[#00c984] hover:scale-[1.01] active:scale-[0.99] disabled:opacity-50"
          data-testid="register-submit"
        >
          {loading ? (
            <Loader2 className="animate-spin" size={16} />
          ) : (
            <>
              Create AHONIX Workspace <ArrowRight size={14} />
            </>
          )}
        </button>
      </form>

      {/* Terms & Privacy */}
      <p className="mt-3.5 text-center text-[11px] leading-relaxed text-[#64748B]">
        By signing up, you agree to our{" "}
        <Link
          to="/terms"
          className="text-[#00E599] hover:underline"
          data-testid="register-terms-link"
        >
          Terms of Service
        </Link>{" "}
        and{" "}
        <Link
          to="/privacy"
          className="text-[#00E599] hover:underline"
          data-testid="register-privacy-link"
        >
          Privacy Policy
        </Link>
        .
      </p>

      {/* Divider */}
      <div className="my-5 flex items-center gap-3 text-[11px] font-mono text-[#475569]">
        <div className="h-px flex-1 bg-[#16221B]" />
        <span>OR</span>
        <div className="h-px flex-1 bg-[#16221B]" />
      </div>

      {/* Google OAuth Button */}
      <GoogleButton label="Sign up with Google" />
    </AuthShell>
  );
}
