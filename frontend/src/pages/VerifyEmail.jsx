import React, { useState, useEffect, useRef } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Loader2, CheckCircle2, AlertCircle, Mail, ArrowRight } from "lucide-react";
import { api, formatApiErrorDetail } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { AuthShell } from "@/pages/AuthShell";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";

export default function VerifyEmail() {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const navigate = useNavigate();
  const { setUser } = useAuth();

  const [status, setStatus] = useState("verifying"); // "verifying" | "success" | "error"
  const [errorMsg, setErrorMsg] = useState("");
  const [resendEmail, setResendEmail] = useState("");
  const [resendLoading, setResendLoading] = useState(false);
  const [resendSuccess, setResendSuccess] = useState(false);
  const attemptedRef = useRef(false);

  useEffect(() => {
    if (!token) {
      setStatus("error");
      setErrorMsg("No verification token was provided in the link.");
      return;
    }

    if (attemptedRef.current) return;
    attemptedRef.current = true;

    const doVerify = async () => {
      try {
        const { data } = await api.post("/auth/verify-email", { token });
        setStatus("success");
        if (data?.user) {
          setUser(data.user);
        }
        toast.success("Email verified successfully! Redirecting to command center...");
        setTimeout(() => {
          navigate(data?.user?.onboarding_completed ? "/app/overview" : "/onboarding", { replace: true });
        }, 1200);
      } catch (err) {
        setStatus("error");
        const msg = formatApiErrorDetail(err.response?.data?.detail) || "This verification link is invalid or has expired.";
        setErrorMsg(msg);
      }
    };

    doVerify();
  }, [token, navigate, setUser]);

  const handleResend = async (e) => {
    e.preventDefault();
    if (!resendEmail) return;
    setResendLoading(true);
    setResendSuccess(false);
    setErrorMsg("");
    try {
      await api.post("/auth/resend-verification", { email: resendEmail });
      setResendSuccess(true);
      toast.success("Verification link dispatched. Please check your inbox.");
    } catch (err) {
      const msg = formatApiErrorDetail(err.response?.data?.detail) || "Unable to resend verification email.";
      setErrorMsg(msg);
    } finally {
      setResendLoading(false);
    }
  };

  return (
    <AuthShell
      title="Email Verification"
      subtitle={
        status === "verifying"
          ? "Validating your verification token..."
          : status === "success"
          ? "Your account has been confirmed."
          : "Verification link expired or invalid."
      }
      footer={
        <Link
          to="/login"
          className="font-semibold text-[#00E599] hover:underline"
          data-testid="link-login"
        >
          Return to sign in
        </Link>
      }
    >
      <div className="space-y-5" data-testid="verify-email-container">
        {status === "verifying" && (
          <div className="flex flex-col items-center justify-center py-8 text-center space-y-4">
            <Loader2 className="animate-spin text-[#00E599]" size={36} />
            <p className="text-xs text-[#94A3B8]">
              Confirming your security token with the AHONIX auth server...
            </p>
          </div>
        )}

        {status === "success" && (
          <div className="flex flex-col items-center justify-center py-8 text-center space-y-4">
            <div className="flex h-16 w-16 items-center justify-center rounded-full border border-[#00E599]/30 bg-[#00E599]/10 text-[#00E599]">
              <CheckCircle2 size={32} />
            </div>
            <div className="space-y-1">
              <h3 className="font-display text-lg font-bold text-[#F8FAFC]">
                Account Verified
              </h3>
              <p className="text-xs text-[#94A3B8]">
                Your email address has been confirmed. Redirecting to your command center...
              </p>
            </div>
          </div>
        )}

        {status === "error" && (
          <div className="space-y-4">
            <div className="flex items-start gap-3 rounded-xl border border-rose-900/50 bg-rose-950/30 p-3.5 text-xs text-rose-300">
              <AlertCircle size={18} className="shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">Verification failed</p>
                <p className="mt-0.5 text-rose-300/90">{errorMsg}</p>
              </div>
            </div>

            {resendSuccess ? (
              <div className="rounded-xl border border-[#00E599]/30 bg-[#00E599]/10 p-4 text-center text-xs text-[#00E599]">
                <CheckCircle2 size={20} className="mx-auto mb-1.5" />
                A fresh verification link has been sent to <strong>{resendEmail}</strong>. Please check your inbox or spam folder.
              </div>
            ) : (
              <form onSubmit={handleResend} className="space-y-3 pt-2">
                <p className="text-xs text-[#94A3B8]">
                  Need a new verification link? Enter your email address below:
                </p>
                <div>
                  <Label className="text-xs font-semibold text-[#94A3B8]">Email Address</Label>
                  <div className="relative mt-1.5">
                    <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-[#64748B]">
                      <Mail size={15} />
                    </div>
                    <input
                      type="email"
                      value={resendEmail}
                      onChange={(e) => setResendEmail(e.target.value)}
                      required
                      placeholder="your-email@example.com"
                      className="h-11 w-full rounded-xl border border-[#16221B] bg-[#0B110E] pl-10 pr-3.5 text-xs text-[#F8FAFC] placeholder:text-[#475569] transition-all focus:border-[#00E599] focus:outline-none focus:ring-1 focus:ring-[#00E599]/30"
                      data-testid="resend-verification-email-input"
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={resendLoading}
                  className="flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-[#00E599] font-display text-xs font-bold text-[#040706] shadow-lg shadow-[#00E599]/20 transition-all hover:bg-[#00c984] disabled:opacity-50"
                  data-testid="resend-verification-btn"
                >
                  {resendLoading ? (
                    <Loader2 className="animate-spin" size={15} />
                  ) : (
                    <>
                      Resend Verification Link <ArrowRight size={14} />
                    </>
                  )}
                </button>
              </form>
            )}
          </div>
        )}
      </div>
    </AuthShell>
  );
}
