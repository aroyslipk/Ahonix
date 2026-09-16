import axios from "axios";

const rawBackendUrl = process.env.REACT_APP_BACKEND_URL;
export const BACKEND_URL = rawBackendUrl ? rawBackendUrl.replace(/\/$/, "") : "";
export const API = BACKEND_URL ? `${BACKEND_URL}/api` : "/api";

export const api = axios.create({
  baseURL: API,
  withCredentials: true,
});

// On an expired/invalid session, send the user back to login (except the
// initial /auth/me probe and the auth endpoints themselves).
api.interceptors.response.use(
  (r) => r,
  (error) => {
    const status = error?.response?.status;
    const url = error?.config?.url || "";
    const isAuthProbe = url.includes("/auth/");
    const isIntegration = url.includes("/integrations/");
    if (status === 401 && !isAuthProbe && !isIntegration && typeof window !== "undefined") {
      const path = window.location.pathname;
      if (path.startsWith("/app")) window.location.assign("/login");
    }
    return Promise.reject(error);
  }
);

export function formatApiErrorDetail(detail) {
  if (detail == null) return "Something went wrong. Please try again.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail
      .map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e)))
      .filter(Boolean)
      .join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}

const CUR = {
  USD: "$", EUR: "€", GBP: "£", CAD: "C$", AUD: "A$", INR: "₹",
};

export function curSymbol(currency = "USD") {
  return CUR[currency] || "$";
}

export function fmtCurrency(n, currency = "USD", compact = false) {
  if (n == null || isNaN(n)) return "—";
  const sym = curSymbol(currency);
  const neg = n < 0;
  let v = Math.abs(n);
  let out;
  if (compact && v >= 1000) {
    if (v >= 1_000_000) out = (v / 1_000_000).toFixed(1) + "M";
    else out = (v / 1000).toFixed(1) + "K";
  } else {
    out = v.toLocaleString("en-US", { maximumFractionDigits: v >= 100 ? 0 : 2 });
  }
  return `${neg ? "-" : ""}${sym}${out}`;
}

export function fmtNumber(n, compact = false) {
  if (n == null || isNaN(n)) return "—";
  if (compact && Math.abs(n) >= 1000) {
    if (Math.abs(n) >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
    return (n / 1000).toFixed(1) + "K";
  }
  return Number(n).toLocaleString("en-US", { maximumFractionDigits: 0 });
}

export function fmtPercent(n) {
  if (n == null || isNaN(n)) return "—";
  return `${Number(n).toFixed(1)}%`;
}

export function fmtValue(kind, value, currency) {
  if (kind === "currency") return fmtCurrency(value, currency);
  if (kind === "percent") return fmtPercent(value);
  if (kind === "ratio") return `${Number(value).toFixed(2)}x`;
  return fmtNumber(value);
}
