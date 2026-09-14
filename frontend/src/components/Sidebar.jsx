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
    <aside className="hidden w-64 shrink-0 flex-col border-r border-[#1E2235] bg-[#0B0D14] md:flex">
      <div className="flex h-16 items-center px-5">
        <Logo size={26} />
      </div>
      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-2">
        {NAV.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            data-testid={item.testid}
            className={({ isActive }) =>
              `group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                isActive
                  ? "bg-emerald-500/10 text-emerald-300"
                  : "text-[#94A3B8] hover:bg-[#161926] hover:text-[#F8FAFC]"
              }`
            }
          >
            {({ isActive }) => (
              <>
                <item.icon size={18} className={isActive ? "text-emerald-400" : "text-[#64748B] group-hover:text-[#94A3B8]"} />
                <span className="flex-1">{item.name}</span>
                {item.badge && (
                  <span className="rounded bg-emerald-500/15 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide text-emerald-300">
                    {item.badge}
                  </span>
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>
      <div className="border-t border-[#1E2235] p-3">
        <div className="flex items-center gap-3 rounded-lg px-2 py-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-emerald-500 to-cyan-500 text-xs font-bold text-emerald-950">
            {(user?.name || "A").slice(0, 1).toUpperCase()}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-[#F8FAFC]">{user?.name || "Merchant"}</p>
            <p className="truncate text-xs text-[#64748B]">{user?.email}</p>
          </div>
          <button
            onClick={async () => {
              await logout();
              navigate("/login");
            }}
            className="rounded-lg p-2 text-[#64748B] hover:bg-[#161926] hover:text-rose-400"
            data-testid="logout-btn"
            title="Sign out"
          >
            <LogOut size={16} />
          </button>
        </div>
      </div>
    </aside>
  );
}
