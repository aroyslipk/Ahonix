import React, { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { api, formatApiErrorDetail } from "@/lib/api";
import { AuthShell } from "@/pages/AuthShell";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";

export default function ResetPassword() {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await api.post("/auth/reset-password", { token, password });
      toast.success("Password updated. Please sign in.");
      navigate("/login", { replace: true });
    } catch (err) {
      setError(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell
      title="Choose a new password"
      subtitle="Enter a new password for your account."
      footer={<Link to="/login" className="font-semibold text-emerald-400 hover:text-emerald-300">Back to sign in</Link>}
    >
      {!token ? (
        <div className="rounded-lg border border-amber-900/50 bg-amber-950/20 px-3 py-3 text-xs text-amber-300">
          This reset link is missing a token. Request a new link from the forgot-password page.
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4" data-testid="reset-form">
          {error && <div className="rounded-lg border border-rose-900/50 bg-rose-950/20 px-3 py-2 text-xs text-rose-300">{error}</div>}
          <div>
            <Label className="text-xs font-medium text-[#94A3B8]">New Password</Label>
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="mt-1.5 border-[#16221B] bg-[#0B110E] text-xs text-[#F8FAFC] transition-colors focus:border-emerald-500/40"
              data-testid="reset-password"
            />
          </div>
          <Button
            type="submit"
            disabled={loading}
            className="w-full bg-emerald-500 font-semibold text-emerald-950 hover:bg-emerald-400"
            data-testid="reset-submit"
          >
            {loading ? <Loader2 className="animate-spin" size={16} /> : "Update Password"}
          </Button>
        </form>
      )}
    </AuthShell>
  );
}

