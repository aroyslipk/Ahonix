import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { api, formatApiErrorDetail } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { AuthShell, GoogleButton } from "@/pages/AuthShell";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

export default function Register() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { setUser } = useAuth();
  const navigate = useNavigate();

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
      subtitle="Start with a fully-loaded demo — no credit card, no data connection required."
      footer={
        <>
          Already have an account?{" "}
          <Link to="/login" className="font-semibold text-emerald-400 hover:text-emerald-300" data-testid="link-login">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={submit} className="space-y-4" data-testid="register-form">
        {error && (
          <div className="rounded-lg border border-rose-900/50 bg-rose-950/20 px-3 py-2 text-sm text-rose-300" data-testid="register-error">
            {error}
          </div>
        )}
        <div>
          <Label className="text-[#94A3B8]">Full name</Label>
          <Input value={name} onChange={(e) => setName(e.target.value)} required
            className="mt-1.5 border-[#2D334B] bg-[#0F111A] text-[#F8FAFC]" data-testid="register-name" />
        </div>
        <div>
          <Label className="text-[#94A3B8]">Email</Label>
          <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required
            className="mt-1.5 border-[#2D334B] bg-[#0F111A] text-[#F8FAFC]" data-testid="register-email" />
        </div>
        <div>
          <Label className="text-[#94A3B8]">Password</Label>
          <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required
            placeholder="At least 6 characters"
            className="mt-1.5 border-[#2D334B] bg-[#0F111A] text-[#F8FAFC]" data-testid="register-password" />
        </div>
        <Button type="submit" disabled={loading}
          className="w-full bg-emerald-500 font-semibold text-emerald-950 hover:bg-emerald-400" data-testid="register-submit">
          {loading ? <Loader2 className="animate-spin" size={16} /> : "Create account"}
        </Button>
      </form>
      <p className="mt-3 text-center text-xs text-[#64748B] leading-relaxed">
        By creating an account, you agree to the{" "}
        <Link to="/terms" className="text-emerald-400 hover:text-emerald-300 hover:underline" data-testid="register-terms-link">
          Terms of Service
        </Link>{" "}
        and acknowledge the{" "}
        <Link to="/privacy" className="text-emerald-400 hover:text-emerald-300 hover:underline" data-testid="register-privacy-link">
          Privacy Policy
        </Link>.
      </p>
      <div className="my-5 flex items-center gap-3 text-xs text-[#475569]">
        <div className="h-px flex-1 bg-[#1E2235]" /> OR <div className="h-px flex-1 bg-[#1E2235]" />
      </div>
      <GoogleButton label="Sign up with Google" />
    </AuthShell>
  );
}
