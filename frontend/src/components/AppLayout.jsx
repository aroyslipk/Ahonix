import React from "react";
import { Outlet, NavLink } from "react-router-dom";
import {
  LayoutDashboard, BrainCircuit, TrendingUp, Boxes, CheckSquare,
} from "lucide-react";
import { Sidebar } from "@/components/Sidebar";
import { TopBar } from "@/components/TopBar";
import { AskAhonix } from "@/components/AskAhonix";
import { WorkspaceProvider } from "@/context/WorkspaceContext";
import { UIProvider } from "@/context/UIContext";

const MOBILE_NAV = [
  { name: "Overview", icon: LayoutDashboard, path: "/app/overview" },
  { name: "AI", icon: BrainCircuit, path: "/app/ai-intelligence" },
  { name: "Sales", icon: TrendingUp, path: "/app/sales" },
  { name: "Stock", icon: Boxes, path: "/app/inventory" },
  { name: "Actions", icon: CheckSquare, path: "/app/action-center" },
];

export function AppLayout() {
  return (
    <UIProvider>
      <WorkspaceProvider>
        <div className="flex min-h-screen bg-[#08090E]">
          <Sidebar />
          <div className="flex min-w-0 flex-1 flex-col">
            <TopBar />
            <main className="flex-1 px-4 pb-24 pt-6 sm:px-6 md:pb-8 lg:px-8">
              <div className="mx-auto max-w-[1400px]">
                <Outlet />
              </div>
            </main>
          </div>
          <AskAhonix />

          {/* mobile bottom nav */}
          <nav className="fixed bottom-0 left-0 right-0 z-30 flex border-t border-[#1E2235] bg-[#0B0D14]/95 backdrop-blur-md md:hidden">
            {MOBILE_NAV.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                className={({ isActive }) =>
                  `flex flex-1 flex-col items-center gap-1 py-2.5 text-[10px] font-medium ${
                    isActive ? "text-emerald-400" : "text-[#64748B]"
                  }`
                }
              >
                <item.icon size={19} />
                {item.name}
              </NavLink>
            ))}
          </nav>
        </div>
      </WorkspaceProvider>
    </UIProvider>
  );
}
