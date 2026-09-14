import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { api, formatApiErrorDetail } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { AuthShell, GoogleButton } from "@/pages/AuthShell";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

export default function Login() {
  const [email, setEmail] = useState("alex@northstargoods.com");
  const [password, setPassword] = useState("Ahonix2026!");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { setUser } = useAuth();
  const navigate = useNavigate();

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const { data } = await api.post("/auth/login", { email, password });
      setUser(data);
      navigate(data.onboarding_completed ? "/app/overview" : "/onboarding", { replace: true });
    } catch (err) {
      setError(formatApiErrorDetail(err.response?.data?.detail) || err.message);
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
          <Link to="/register" className="font-semibold text-emerald-400 hover:text-emerald-300" data-testid="link-register">
            Create an account
          </Link>
        </>
      }
    >
      <form onSubmit={submit} className="space-y-4" data-testid="login-form">
        {error && (
          <div className="rounded-lg border border-rose-900/50 bg-rose-950/20 px-3 py-2 text-sm text-rose-300" data-testid="login-error">
            {error}
          </div>
        )}
        <div>
          <Label className="text-[#94A3B8]">Email</Label>
          <Input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="mt-1.5 border-[#2D334B] bg-[#0F111A] text-[#F8FAFC]"
            data-testid="login-email"
          />
        </div>
        <div>
          <div className="flex items-center justify-between">
            <Label className="text-[#94A3B8]">Password</Label>
            <Link to="/forgot-password" className="text-xs text-emerald-400 hover:text-emerald-300" data-testid="link-forgot">
              Forgot?
            </Link>
          </div>
          <Input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className="mt-1.5 border-[#2D334B] bg-[#0F111A] text-[#F8FAFC]"
            data-testid="login-password"
          />
        </div>
        <Button
          type="submit"
          disabled={loading}
          className="w-full bg-emerald-500 font-semibold text-emerald-950 hover:bg-emerald-400"
          data-testid="login-submit"
        >
          {loading ? <Loader2 className="animate-spin" size={16} /> : "Sign in"}
        </Button>
      </form>
      <div className="my-5 flex items-center gap-3 text-xs text-[#475569]">
        <div className="h-px flex-1 bg-[#1E2235]" /> OR <div className="h-px flex-1 bg-[#1E2235]" />
      </div>
      <GoogleButton />
      <p className="mt-4 rounded-lg bg-[#0F111A] px-3 py-2 text-center text-xs text-[#64748B]">
        Demo login prefilled · explore the full product instantly
      </p>
      <div className="mt-5 flex items-center justify-center gap-4 text-xs text-[#64748B]">
        <Link to="/privacy" className="transition-colors hover:text-[#94A3B8] hover:underline" data-testid="login-privacy-link">
          Privacy Policy
        </Link>
        <span>·</span>
        <Link to="/terms" className="transition-colors hover:text-[#94A3B8] hover:underline" data-testid="login-terms-link">
          Terms of Service
        </Link>
      </div>
    </AuthShell>
  );
}
