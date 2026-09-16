import React from "react";
import { NavLink, useNavigate } from "react-router-dom";
import {
  LayoutDashboard, BrainCircuit, Wallet, TrendingUp, Package, Boxes, Target,
  Users, Truck, Globe, CheckSquare, Settings, LogOut,
} from "lucide-react";
import { Logo } from "@/components/Logo";
import { useAuth } from "@/context/AuthContext";

export const NAV = [
  { name: "Overview", icon: LayoutDashboard, path: "/app/overview", testid: "nav-overview" },
  { name: "AI Intelligence", icon: BrainCircuit, path: "/app/ai-intelligence", testid: "nav-ai-intelligence", badge: "X-Ray" },
  { name: "True Profit", icon: Wallet, path: "/app/profit", testid: "nav-true-profit" },
  { name: "Sales", icon: TrendingUp, path: "/app/sales", testid: "nav-sales" },
  { name: "Products", icon: Package, path: "/app/products", testid: "nav-products" },
  { name: "Inventory", icon: Boxes, path: "/app/inventory", testid: "nav-inventory" },
  { name: "Marketing", icon: Target, path: "/app/marketing", testid: "nav-marketing" },
  { name: "Customers", icon: Users, path: "/app/customers", testid: "nav-customers" },
  { name: "Operations", icon: Truck, path: "/app/operations", testid: "nav-operations" },
  { name: "Markets", icon: Globe, path: "/app/markets", testid: "nav-markets" },
  { name: "Action Center", icon: CheckSquare, path: "/app/action-center", testid: "nav-action-center" },
  { name: "Settings", icon: Settings, path: "/app/settings", testid: "nav-settings" },
];

export function Sidebar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <aside className="hidden w-64 shrink-0 flex-col border-r border-white/[0.06] bg-[#070C0A] md:flex select-none">
      {/* Brand Header */}
      <div className="flex h-16 items-center px-6 border-b border-white/[0.04]">
        <Logo size={24} />
      </div>

      {/* Navigation List */}
      <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 py-3">
        {NAV.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            data-testid={item.testid}
            className={({ isActive }) =>
              `group relative flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-medium transition-all duration-150 ${
                isActive
                  ? "bg-[#0B1612] text-[#00E599] shadow-sm"
                  : "text-[#94A3B8] hover:bg-[#0C120F] hover:text-[#F8FAFC]"
              }`
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <span className="absolute left-0 top-2 bottom-2 w-1 rounded-r-full bg-[#00E599]" />
                )}
                <item.icon
                  size={17}
                  className={`transition-colors ${
                    isActive
                      ? "text-[#00E599]"
                      : "text-[#64748B] group-hover:text-[#94A3B8]"
                  }`}
                />
                <span className="flex-1 truncate">{item.name}</span>
                {item.badge && (
                  <span className="rounded bg-[#00E599]/10 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-[#00E599]">
                    {item.badge}
                  </span>
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Merchant Profile Footer */}
      <div className="border-t border-white/[0.06] p-3">
        <div className="flex items-center gap-3 rounded-xl bg-[#0B110E] border border-white/[0.05] p-2.5">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[#008060] text-xs font-bold text-white">
            {(user?.name || "A").slice(0, 1).toUpperCase()}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-semibold text-[#F8FAFC]">{user?.name || "Merchant"}</p>
            <p className="truncate text-[11px] text-[#64748B]">{user?.email}</p>
          </div>
          <button
            onClick={async () => {
              await logout();
              navigate("/login");
            }}
            className="rounded-lg p-1.5 text-[#64748B] transition-colors hover:bg-white/10 hover:text-rose-400"
            data-testid="logout-btn"
            title="Sign out"
          >
            <LogOut size={15} />
          </button>
        </div>
      </div>
    </aside>
  );
}
