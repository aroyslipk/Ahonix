import React, { useEffect, useRef } from "react";
import {
  BrowserRouter, Routes, Route, Navigate, useLocation, useNavigate,
} from "react-router-dom";
import { Loader2 } from "lucide-react";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import { Toaster } from "@/components/ui/sonner";

import Landing from "@/pages/Landing";
import Login from "@/pages/Login";
import Register from "@/pages/Register";
import ForgotPassword from "@/pages/ForgotPassword";
import ResetPassword from "@/pages/ResetPassword";
import Onboarding from "@/pages/Onboarding";
import { AppLayout } from "@/components/AppLayout";
import Overview from "@/pages/Overview";
import AIIntelligence from "@/pages/AIIntelligence";
import TrueProfit from "@/pages/TrueProfit";
import Sales from "@/pages/Sales";
import Products from "@/pages/Products";
import ProductDetail from "@/pages/ProductDetail";
import Inventory from "@/pages/Inventory";
import Marketing from "@/pages/Marketing";
import Customers from "@/pages/Customers";
import Operations from "@/pages/Operations";
import Markets from "@/pages/Markets";
import ActionCenter from "@/pages/ActionCenter";
import Settings from "@/pages/Settings";
import PrivacyPolicy from "@/pages/PrivacyPolicy";
import TermsOfService from "@/pages/TermsOfService";

function FullLoader() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#08090E]">
      <Loader2 className="animate-spin text-emerald-400" size={28} />
    </div>
  );
}

function AuthCallback() {
  const navigate = useNavigate();
  const location = useLocation();
  const { setUser } = useAuth();
  const processed = useRef(false);

  useEffect(() => {
    if (processed.current) return;
    processed.current = true;
    const hash = location.hash || "";
    const search = location.search || "";
    const sid =
      new URLSearchParams(hash.replace(/^#/, "")).get("session_id") ||
      new URLSearchParams(search).get("session_id");

    (async () => {
      try {
        if (sid) {
          const { data } = await api.post("/auth/session", { session_id: sid });
          setUser(data);
          window.history.replaceState(null, "", window.location.pathname);
          navigate(data.onboarding_completed ? "/app/overview" : "/onboarding", { replace: true });
        } else {
          // Direct cookie verification fallback
          const { data } = await api.get("/auth/me");
          setUser(data);
          navigate(data.onboarding_completed ? "/app/overview" : "/onboarding", { replace: true });
        }
      } catch {
        navigate("/login", { replace: true });
      }
    })();
  }, [location.hash, location.search, navigate, setUser]);

  return <FullLoader />;
}

function ProtectedRoute({ children, requireOnboarding = true }) {
  const { user, loading } = useAuth();
  if (loading) return <FullLoader />;
  if (!user) return <Navigate to="/login" replace />;
  if (requireOnboarding && !user.onboarding_completed) return <Navigate to="/onboarding" replace />;
  return children;
}

function PublicOnly({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <FullLoader />;
  if (user) return <Navigate to={user.onboarding_completed ? "/app/overview" : "/onboarding"} replace />;
  return children;
}

function AppRouter() {
  const location = useLocation();
  if (
    location.hash?.includes("session_id=") ||
    location.search?.includes("session_id=") ||
    location.pathname === "/auth/callback"
  ) {
    return <AuthCallback />;
  }

  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<PublicOnly><Login /></PublicOnly>} />
      <Route path="/register" element={<PublicOnly><Register /></PublicOnly>} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route path="/auth/callback" element={<AuthCallback />} />
      <Route path="/privacy" element={<PrivacyPolicy />} />
      <Route path="/terms" element={<TermsOfService />} />
      <Route
        path="/onboarding"
        element={
          <ProtectedRoute requireOnboarding={false}>
            <Onboarding />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app"
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/app/overview" replace />} />
        <Route path="overview" element={<Overview />} />
        <Route path="ai-intelligence" element={<AIIntelligence />} />
        <Route path="profit" element={<TrueProfit />} />
        <Route path="sales" element={<Sales />} />
        <Route path="products" element={<Products />} />
        <Route path="products/:id" element={<ProductDetail />} />
        <Route path="inventory" element={<Inventory />} />
        <Route path="marketing" element={<Marketing />} />
        <Route path="customers" element={<Customers />} />
        <Route path="operations" element={<Operations />} />
        <Route path="markets" element={<Markets />} />
        <Route path="action-center" element={<ActionCenter />} />
        <Route path="settings" element={<Settings />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRouter />
        <Toaster position="top-right" theme="dark" />
      </BrowserRouter>
    </AuthProvider>
  );
}
