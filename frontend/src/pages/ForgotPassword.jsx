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
      subtitle="Enter your email and we'll send a reset link."
      footer={
        <Link to="/login" className="font-semibold text-emerald-400 hover:text-emerald-300">
          Back to sign in
        </Link>
      }
    >
      {sent ? (
        <div className="rounded-xl border border-emerald-900/40 bg-emerald-950/20 p-5 text-center" data-testid="forgot-success">
          <CheckCircle2 className="mx-auto mb-3 text-emerald-400" size={28} />
          <p className="text-sm text-[#CBD5E1]">
            If an account exists for <span className="font-semibold text-[#F8FAFC]">{email}</span>, a reset link has
            been generated. In this demo the link is logged server-side.
          </p>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4" data-testid="forgot-form">
          {error && <div className="rounded-lg border border-rose-900/50 bg-rose-950/20 px-3 py-2 text-sm text-rose-300">{error}</div>}
          <div>
            <Label className="text-[#94A3B8]">Email</Label>
            <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required
              className="mt-1.5 border-[#2D334B] bg-[#0F111A] text-[#F8FAFC]" data-testid="forgot-email" />
          </div>
          <Button type="submit" disabled={loading}
            className="w-full bg-emerald-500 font-semibold text-emerald-950 hover:bg-emerald-400" data-testid="forgot-submit">
            {loading ? <Loader2 className="animate-spin" size={16} /> : "Send reset link"}
          </Button>
        </form>
      )}
    </AuthShell>
  );
}
