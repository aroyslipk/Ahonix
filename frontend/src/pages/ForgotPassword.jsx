import React, { useState } from "react";
import { Link } from "react-router-dom";
import { Loader2, CheckCircle2 } from "lucide-react";
import { api, formatApiErrorDetail } from "@/lib/api";
import { AuthShell } from "@/pages/AuthShell";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await api.post("/auth/forgot-password", { email });
      setSent(true);
    } catch (err) {
      setError(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell
      title="Reset your password"
      subtitle="Enter your verified email to receive an institutional reset link."
      footer={
        <Link to="/login" className="font-semibold text-emerald-400 hover:text-emerald-300">
          Back to sign in
        </Link>
      }
    >
      {sent ? (
        <div className="rounded-xl border border-emerald-500/20 bg-[#0B1A13] p-5 text-center" data-testid="forgot-success">
          <CheckCircle2 className="mx-auto mb-3 text-emerald-400" size={28} />
          <p className="text-xs leading-relaxed text-[#CBD5E1]">
            If an account exists for <span className="font-semibold text-[#F8FAFC]">{email}</span>, a secure password reset link has been dispatched.
          </p>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4" data-testid="forgot-form">
          {error && <div className="rounded-lg border border-rose-900/50 bg-rose-950/20 px-3 py-2 text-xs text-rose-300">{error}</div>}
          <div>
            <Label className="text-xs font-medium text-[#94A3B8]">Email Address</Label>
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="mt-1.5 border-[#16221B] bg-[#0B110E] text-xs text-[#F8FAFC] transition-colors focus:border-emerald-500/40"
              data-testid="forgot-email"
            />
          </div>
          <Button
            type="submit"
            disabled={loading}
            className="w-full bg-emerald-500 font-semibold text-emerald-950 hover:bg-emerald-400"
            data-testid="forgot-submit"
          >
            {loading ? <Loader2 className="animate-spin" size={16} /> : "Send Reset Link"}
          </Button>
        </form>
      )}
    </AuthShell>
  );
}

